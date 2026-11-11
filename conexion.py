"""Capa 0 · Conexión con la mesa: TCP + JSON Lines, saludo, despacho y reconexión.

Lo que hace (docs/protocolo.md, docs/guia-del-bot.md):
  - Acumula bytes en un buffer y corta por '\\n' (un recv puede traer media
    línea o dos y media).
  - Saludo con la versión exacta "1.0.0" y lectura de la bienvenida (id_jugador
    y silla: el token NO es el id).
  - Aguanta silencios largos entre rondas (sin timeout de lectura; keepalive
    TCP para notar una red muerta).
  - Reconecta solo, con backoff y el MISMO token, si se cae el socket. Mientras
    estuvo afuera la mesa jugó por nosotros (check/fold) y la silla sigue
    ocupada: al volver retomamos silla y fichas.
  - Solo `solicitar_accion` se responde. Un tipo de mensaje desconocido se ignora.
  - Una acción que no esté en `acciones_validas` nunca sale: se cambia por la
    acción segura.
"""

import json
import random
import socket
import sys
import time
import traceback

from estado import accion_es_valida, accion_segura

VERSION_PROTOCOLO = "1.0.0"
MOTIVO_MESA_SATURADA = "demasiadas conexiones esperando el saludo"
MAX_LINEA_MESA = 1 << 20          # protocolo.MaxLineaMesa: 1 MiB


class MesaRechazo(Exception):
    """La mesa respondió al saludo con un error definitivo (token inválido,
    versión distinta, mesa llena). Reintentar no lo arregla."""


class Conexion:
    """Un socket con la mesa y su buffer de líneas."""

    def __init__(self, host, puerto, token, params_conexion):
        self.host = host
        self.puerto = puerto
        self.token = token
        self.cfg = params_conexion
        self.sock = None
        self._buf = bytearray()
        self.id_jugador = None
        self.silla = -1

    # --- Apertura y saludo ---
    def abrir(self):
        """Conecta, saluda y lee la bienvenida. Lanza MesaRechazo (definitivo),
        MesaSaturada-como-OSError (pasajero) u OSError (red)."""
        self.cerrar()
        sock = socket.create_connection((self.host, self.puerto), timeout=5)
        self.sock = sock
        self._buf = bytearray()
        sock.settimeout(self.cfg["timeout_saludo_s"])      # solo durante el saludo
        self._activar_keepalive(sock)
        # Ojo: el saludo lleva el token y NO se registra en ningún log.
        self.enviar({"tipo": "saludo", "version": VERSION_PROTOCOLO, "token": self.token})
        bienvenida = self.recibir()
        if bienvenida is None:
            raise OSError("la mesa cerró la conexión durante el saludo")
        if bienvenida.get("tipo") == "error":
            motivo = bienvenida.get("mensaje", "sin detalle")
            if motivo == MOTIVO_MESA_SATURADA:
                raise OSError(motivo)             # pasajero: se reintenta
            raise MesaRechazo(motivo)
        if bienvenida.get("tipo") != "bienvenida":
            raise MesaRechazo(f"se esperaba bienvenida y llegó {bienvenida.get('tipo')!r}")
        self.id_jugador = bienvenida.get("id_jugador") or self.token
        self.silla = bienvenida.get("silla", -1)
        # Después del saludo hay que poder esperar sin límite: entre una mesa y
        # la siguiente no llega nada (y tampoco si nos eliminaron).
        sock.settimeout(None)
        return bienvenida

    def _activar_keepalive(self, sock):
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if hasattr(sock, "ioctl"):      # Windows: (activar, espera ms, intervalo ms)
                sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, int(self.cfg["keepalive_s"] * 1000), 10000))
        except (OSError, AttributeError, ValueError):
            pass

    # --- Mensajes ---
    def enviar(self, mensaje):
        datos = (json.dumps(mensaje, separators=(",", ":")) + "\n").encode("utf-8")
        self.sock.sendall(datos)

    def recibir(self):
        """Siguiente mensaje JSON, o None si la mesa cerró (fin normal de una
        partida, no un error). Una línea que no es JSON se descarta."""
        while True:
            indice = self._buf.find(b"\n")
            if indice >= 0:
                linea = bytes(self._buf[:indice]).strip()
                del self._buf[:indice + 1]
                if not linea:
                    continue
                try:
                    mensaje = json.loads(linea.decode("utf-8-sig"))
                except (ValueError, UnicodeDecodeError):
                    continue
                if isinstance(mensaje, dict):
                    return mensaje
                continue
            if len(self._buf) > 2 * MAX_LINEA_MESA:
                raise OSError("línea de la mesa demasiado larga")
            datos = self.sock.recv(65536)
            if not datos:
                return None
            self._buf += datos

    def cerrar(self):
        try:
            if self.sock is not None:
                self.sock.close()
        except OSError:
            pass
        self.sock = None


class Cliente:
    """Bucle principal: conectar, atender mensajes y reconectar si se cae.

    `manejador` implementa:
        al_conectar(id_jugador, silla, reconexion: bool)
        al_mensaje(mensaje)                       # informativos
        decidir(mensaje) -> accion (dict)         # solicitar_accion
    """

    def __init__(self, direccion, token, manejador, params, registro):
        host, puerto = direccion.rsplit(":", 1)
        self.cfg = params["conexion"]
        self.log_mensajes = params["registro"]["mensajes"]
        self.conexion = Conexion(host or "127.0.0.1", int(puerto), token, self.cfg)
        self.manejador = manejador
        self.registro = registro
        self._ultimo_tipo = None
        self._conectado_antes = False

    # --- Conexión con reintentos ---
    def _abrir_con_reintentos(self, presupuesto_s):
        limite = time.monotonic() + presupuesto_s
        intento = 0
        while True:
            try:
                self.conexion.abrir()
                return
            except MesaRechazo:
                raise
            except OSError as error:
                self.conexion.cerrar()
                if time.monotonic() >= limite:
                    raise ConnectionError(f"no se pudo conectar tras {presupuesto_s:.0f} s: {error}") from error
                # Backoff creciente (0,1 s, 0,2 s, 0,4 s... hasta el tope) con hasta 50 % de azar.
                pausa = min(0.1 * (2 ** intento), self.cfg["espera_max_s"])
                pausa += random.random() * pausa / 2
                intento += 1
                time.sleep(pausa)

    def correr(self):
        """Devuelve el código de salida: 0 si la mesa cerró normalmente, 1 si no
        se pudo conectar o la mesa rechazó el saludo."""
        presupuesto = self.cfg["inicial_s"]
        while True:
            try:
                self._abrir_con_reintentos(presupuesto)
            except MesaRechazo as error:
                self.registro.log(f"la mesa rechazó la conexión: {error}")
                return 1
            except ConnectionError as error:
                self.registro.log(str(error))
                return 0 if self._conectado_antes and self._ultimo_tipo == "mano_fin" else 1

            reconexion = self._conectado_antes
            self._conectado_antes = True
            c = self.conexion
            self.registro.log(f"{'reconectado' if reconexion else 'conectado'} como {c.id_jugador} en la silla {c.silla}")
            self.registro.escribir("conexion", reconexion=reconexion, id_jugador=c.id_jugador, silla=c.silla)
            try:
                self.manejador.al_conectar(c.id_jugador, c.silla, reconexion)
            except Exception:
                self.registro.escribir("error", donde="al_conectar", traza=traceback.format_exc())

            motivo = self._atender()
            self.conexion.cerrar()
            # Si la mesa cerró justo después de un mano_fin, lo más probable es
            # que la partida terminó: se reintenta poco rato. Si no (a mitad de
            # mano, error de red), puede ser una caída: se insiste más.
            if motivo == "eof" and self._ultimo_tipo == "mano_fin":
                presupuesto = self.cfg["fin_s"]
                self.registro.log("la mesa cerró tras una mano; pruebo a volver un rato por si fue una caída")
            else:
                presupuesto = self.cfg["caida_s"]
                self.registro.log(f"conexión perdida ({motivo}); reconectando con el mismo token")

    # --- Atender mensajes ---
    def _atender(self):
        """Lee y despacha hasta que se cierre el socket. Devuelve "eof" o "error"."""
        while True:
            try:
                mensaje = self.conexion.recibir()
            except OSError as error:
                self.registro.escribir("red", error=str(error))
                return "error"
            if mensaje is None:
                return "eof"

            tipo = mensaje.get("tipo")
            self._ultimo_tipo = tipo
            if self.log_mensajes:
                self.registro.escribir("msg", msg=mensaje)

            if tipo == "solicitar_accion":
                accion = self._decidir(mensaje)
                estado = mensaje.get("estado") or {}
                try:
                    self.conexion.enviar({
                        "tipo": "accion", "version": VERSION_PROTOCOLO,
                        "id_mano": estado.get("id_mano", ""), "accion": accion,
                    })
                except OSError as error:
                    self.registro.escribir("red", error=str(error))
                    return "error"
            elif tipo == "error":
                self.registro.log(f"la mesa avisó un error: {mensaje.get('mensaje', '')}")
            else:
                # estado, mano_inicio, mano_fin, bienvenida repetida, tipos nuevos...
                # Informativos: nunca se responden.
                try:
                    self.manejador.al_mensaje(mensaje)
                except Exception:
                    self.registro.escribir("error", donde="al_mensaje", tipo_msg=tipo, traza=traceback.format_exc())

    def _decidir(self, mensaje):
        """Pide la decisión al manejador. Toda excepción cae en la acción
        segura; el resultado se valida contra `acciones_validas`."""
        validas = mensaje.get("acciones_validas") or []
        inicio = time.perf_counter()
        try:
            accion = self.manejador.decidir(mensaje)
        except Exception:
            self.registro.escribir("error", donde="decidir", traza=traceback.format_exc())
            print(traceback.format_exc(), file=sys.stderr, flush=True)
            accion = accion_segura(validas)
        if not accion_es_valida(accion, validas):
            self.registro.escribir("accion_invalida", accion=accion, validas=validas)
            accion = accion_segura(validas)
        self.registro.escribir("respuesta", accion=accion, tiempo_s=round(time.perf_counter() - inicio, 4))
        return accion
