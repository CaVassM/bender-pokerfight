"""Pruebas de conexion.py contra una mesa falsa en un hilo: framing por líneas,
saludo, eco del id_mano, acción segura ante excepciones y reconexión con el mismo token."""

import json
import socket
import threading

from conexion import Cliente
from params import cargar_params
from registro import Registro

ESTADO = {
    "id_mano": "m-1", "etapa": "preflop", "comunitarias": [], "pozo": 150, "apuesta_actual": 100,
    "subida_minima": 100, "ciega_chica": 50, "ciega_grande": 100, "posicion_boton": 0,
    "jugadores": [{"id": "yo", "saldo": 9950, "apuesta_ronda": 50, "activo": True, "en_torneo": True, "en_mano": True, "posicion_silla": 0},
                  {"id": "r", "saldo": 9900, "apuesta_ronda": 100, "activo": True, "en_torneo": True, "en_mano": True, "posicion_silla": 1}],
    "historial_acciones": [],
}


def linea(obj):
    return (json.dumps(obj) + "\n").encode()


class MesaFalsa:
    """Acepta conexiones y ejecuta un guion por conexión (lista de funciones f(sock, lector))."""

    def __init__(self, guiones):
        self.servidor = socket.socket()
        self.servidor.bind(("127.0.0.1", 0))
        self.servidor.listen(4)
        self.puerto = self.servidor.getsockname()[1]
        self.guiones = guiones
        self.saludos = []
        self.acciones = []
        self.hilo = threading.Thread(target=self._servir, daemon=True)
        self.hilo.start()

    def _servir(self):
        for guion in self.guiones:
            self.servidor.settimeout(10)
            try:
                sock, _ = self.servidor.accept()
            except OSError:
                return
            lector = sock.makefile("rb")
            self.saludos.append(json.loads(lector.readline()))
            guion(self, sock, lector)
            # El makefile mantiene vivo el socket: hay que cerrarlo también para
            # que el cliente vea el EOF de verdad.
            lector.close()
            sock.close()
        # Sin más guiones, la mesa "desaparece": las reconexiones reciben rechazo de red.
        self.servidor.close()

    def cerrar(self):
        self.servidor.close()


def params_rapidos():
    p = cargar_params()
    p["conexion"].update({"inicial_s": 3.0, "caida_s": 0.5, "fin_s": 0.5, "espera_max_s": 0.05, "timeout_saludo_s": 3.0})
    return p


class ManejadorFijo:
    def __init__(self, accion=None, falla=False):
        self.accion, self.falla = accion, falla
        self.conexiones, self.recibidos = [], []

    def al_conectar(self, id_jugador, silla, reconexion):
        self.conexiones.append((id_jugador, silla, reconexion))

    def al_mensaje(self, mensaje):
        self.recibidos.append(mensaje["tipo"])

    def decidir(self, mensaje):
        if self.falla:
            raise RuntimeError("boom")
        return self.accion


def solicitar(validas):
    return {"tipo": "solicitar_accion", "version": "1.0.0", "acciones_validas": validas, "timeout_ms": 5000, "estado": ESTADO}


def test_framing_saludo_eco_y_reconexion(tmp_path):
    def conexion1(mesa, sock, lector):
        bienvenida = linea({"tipo": "bienvenida", "version": "1.0.0", "id_jugador": "yo", "silla": 3, "mensaje": "hola"})
        sock.sendall(bienvenida[:17])                      # media línea...
        sock.sendall(bienvenida[17:] + linea({"tipo": "estado", "version": "1.0.0", "estado": ESTADO})[:10])
        resto = linea({"tipo": "estado", "version": "1.0.0", "estado": ESTADO})[10:]
        # ...y un mensaje desconocido + la solicitud, pegados en un solo envío
        sock.sendall(resto + linea({"tipo": "tipo_futuro", "x": 1}) + linea(solicitar(["fold", "call", "raise"])))
        mesa.acciones.append(json.loads(lector.readline()))
        # El cierre brusco debe disparar la reconexión

    def conexion2(mesa, sock, lector):
        sock.sendall(linea({"tipo": "bienvenida", "version": "1.0.0", "id_jugador": "yo", "silla": 3, "mensaje": "de vuelta"}))
        sock.sendall(linea(solicitar(["fold", "check"])))
        mesa.acciones.append(json.loads(lector.readline()))
        sock.sendall(linea({"tipo": "mano_fin", "version": "1.0.0", "resultado": {"id_mano": "m-1", "repartos": []}}))

    mesa = MesaFalsa([conexion1, conexion2])
    manejador = ManejadorFijo(accion={"tipo": "call"})
    registro = Registro(str(tmp_path / "s.jsonl"), eco_stderr=False)
    cliente = Cliente(f"127.0.0.1:{mesa.puerto}", "tok-secreto", manejador, params_rapidos(), registro)

    codigo = cliente.correr()
    registro.cerrar()
    mesa.cerrar()

    # El saludo lleva la versión exacta y el token; las dos conexiones usan el MISMO token.
    assert [s["token"] for s in mesa.saludos] == ["tok-secreto", "tok-secreto"]
    assert all(s["version"] == "1.0.0" for s in mesa.saludos)
    # Eco del id_mano y la acción pedida (call es válida en la primera; en la segunda no
    # lo es -> acción segura: check)
    assert mesa.acciones[0]["accion"] == {"tipo": "call"} and mesa.acciones[0]["id_mano"] == "m-1"
    assert mesa.acciones[1]["accion"] == {"tipo": "check"}
    # Silla recuperada y reconexión anotada
    assert manejador.conexiones == [("yo", 3, False), ("yo", 3, True)]
    # Los mensajes informativos llegaron enteros (el partido en dos pedazos incluido); el
    # desconocido se entregó como informativo sin responderse
    assert manejador.recibidos.count("estado") == 1 and "tipo_futuro" in manejador.recibidos
    assert "mano_fin" in manejador.recibidos
    # Tras un mano_fin + cierre, sin nadie del otro lado: sale en limpio
    assert codigo == 0
    # El token jamás aparece en el log
    assert "tok-secreto" not in (tmp_path / "s.jsonl").read_text(encoding="utf-8")


def test_una_excepcion_en_la_decision_juega_la_accion_segura(tmp_path):
    def guion(mesa, sock, lector):
        sock.sendall(linea({"tipo": "bienvenida", "version": "1.0.0", "id_jugador": "yo", "silla": 0}))
        sock.sendall(linea(solicitar(["fold", "call", "raise", "allin"])))
        mesa.acciones.append(json.loads(lector.readline()))
        sock.sendall(linea(solicitar(["fold", "check", "bet", "allin"])))
        mesa.acciones.append(json.loads(lector.readline()))
        sock.sendall(linea({"tipo": "mano_fin", "version": "1.0.0", "resultado": {}}))

    mesa = MesaFalsa([guion])
    registro = Registro(str(tmp_path / "s.jsonl"), eco_stderr=False)
    cliente = Cliente(f"127.0.0.1:{mesa.puerto}", "t", ManejadorFijo(falla=True), params_rapidos(), registro)
    cliente.correr()
    registro.cerrar()
    mesa.cerrar()
    assert [a["accion"]["tipo"] for a in mesa.acciones] == ["fold", "check"]


def test_una_accion_invalida_se_cambia_por_la_segura(tmp_path):
    def guion(mesa, sock, lector):
        sock.sendall(linea({"tipo": "bienvenida", "version": "1.0.0", "id_jugador": "yo", "silla": 0}))
        sock.sendall(linea(solicitar(["fold", "check"])))
        mesa.acciones.append(json.loads(lector.readline()))
        sock.sendall(linea({"tipo": "mano_fin", "version": "1.0.0", "resultado": {}}))

    mesa = MesaFalsa([guion])
    registro = Registro(str(tmp_path / "s.jsonl"), eco_stderr=False)
    cliente = Cliente(f"127.0.0.1:{mesa.puerto}", "t", ManejadorFijo(accion={"tipo": "raise", "monto": 500}), params_rapidos(), registro)
    cliente.correr()
    registro.cerrar()
    mesa.cerrar()
    assert mesa.acciones[0]["accion"] == {"tipo": "check"}
    assert "accion_invalida" in (tmp_path / "s.jsonl").read_text(encoding="utf-8")


def test_mesa_saturada_se_reintenta(tmp_path):
    def saturada(mesa, sock, lector):
        sock.sendall(linea({"tipo": "error", "version": "1.0.0", "mensaje": "demasiadas conexiones esperando el saludo"}))

    def buena(mesa, sock, lector):
        sock.sendall(linea({"tipo": "bienvenida", "version": "1.0.0", "id_jugador": "yo", "silla": 1}))
        sock.sendall(linea({"tipo": "mano_fin", "version": "1.0.0", "resultado": {}}))

    mesa = MesaFalsa([saturada, buena])
    manejador = ManejadorFijo()
    registro = Registro(str(tmp_path / "s.jsonl"), eco_stderr=False)
    cliente = Cliente(f"127.0.0.1:{mesa.puerto}", "t", manejador, params_rapidos(), registro)
    cliente.correr()
    registro.cerrar()
    mesa.cerrar()
    assert manejador.conexiones[0] == ("yo", 1, False)


def test_rechazo_definitivo_no_reintenta(tmp_path):
    def rechazo(mesa, sock, lector):
        sock.sendall(linea({"tipo": "error", "version": "1.0.0", "mensaje": "mesa: versión de protocolo incompatible"}))

    mesa = MesaFalsa([rechazo])
    registro = Registro(str(tmp_path / "s.jsonl"), eco_stderr=False)
    cliente = Cliente(f"127.0.0.1:{mesa.puerto}", "t", ManejadorFijo(), params_rapidos(), registro)
    assert cliente.correr() == 1
    registro.cerrar()
    mesa.cerrar()
    assert len(mesa.saludos) == 1
