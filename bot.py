"""Bender · el manejador de mensajes (une la conexión con la estrategia).

Interpreta el estado, lleva la cuenta de la mesa y de la mano, decide con la
Capa 1 (capa1.py), registra cada decisión con su tabla de EV, su tiempo y su N, y
nunca se cae: toda decisión va en try/except con la acción segura de respaldo
(aquí y en conexion.Cliente._decidir). La Capa 2 se enchufa en `_estrategia`.
"""

import time
import traceback

from capa1 import Capa1
from estado import (EstadoPublico, SeguimientoMesa, Turno, accion_segura, carta_de_dict,
                    texto_cartas)


class Bender:
    def __init__(self, params, registro):
        self.params = params
        self.registro = registro
        self.mi_id = None
        self.silla = -1
        self.mesa = SeguimientoMesa()
        self.capa1 = Capa1(params)

    # --- Conexión ---
    def al_conectar(self, id_jugador, silla, reconexion):
        self.mi_id = id_jugador
        self.silla = silla
        # Si reconectamos dentro del mismo proceso conservamos las cartas de la
        # mano en curso. Si el proceso es nuevo (kill + relanzar) no hay cartas
        # hasta el próximo mano_inicio: se juega la acción segura.

    # --- Mensajes informativos ---
    def al_mensaje(self, mensaje):
        tipo = mensaje.get("tipo")
        if tipo == "mano_inicio":
            estado = EstadoPublico.de_dict(mensaje.get("estado"))
            cartas = [carta_de_dict(c) for c in mensaje.get("cartas") or []]
            self.mesa.nueva_mano(estado, cartas)
            self.registro.escribir("mano_inicio", id_mano=estado.id_mano, cartas=texto_cartas(cartas),
                                   mesa_manos=self.mesa.manos_mesa, mesa_s=round(self.mesa.segundos_mesa, 1))
        elif tipo == "estado":
            self.mesa.ultimo_estado = EstadoPublico.de_dict(mensaje.get("estado"))
        elif tipo == "mano_fin":
            self.mesa.mano_terminada()
            resultado = mensaje.get("resultado") or {}
            mio = sum(r.get("monto", 0) for r in resultado.get("repartos", []) if r.get("id_jugador") == self.mi_id)
            self.registro.escribir("mano_fin", id_mano=resultado.get("id_mano"), gane=mio,
                                   mostradas=bool(resultado.get("mostradas")))

    # --- Decisión ---
    def decidir(self, mensaje):
        inicio = time.perf_counter()
        if self.params["debug"]["retardo_s"] > 0:
            time.sleep(self.params["debug"]["retardo_s"])      # solo para pruebas
        estado = EstadoPublico.de_dict(mensaje.get("estado"))
        validas = mensaje.get("acciones_validas") or []
        self.mesa.ultimo_estado = estado

        info = {}
        if not self.mesa.tengo_cartas(estado):
            # Reconexión a mitad de mano (o mano_inicio perdido): sin cartas no
            # se puede decidir nada con criterio.
            accion, motivo = accion_segura(validas), "sin cartas de esta mano: acción segura"
            turno = Turno(estado, self.mi_id, [], validas, mensaje.get("timeout_ms", 0))
        else:
            turno = Turno(estado, self.mi_id, self.mesa.mano, validas, mensaje.get("timeout_ms", 0))
            try:
                accion, motivo, info = self._estrategia(turno)
            except Exception:
                # Un fallo de la estrategia no puede tumbar la decisión: acción segura + traza en el log.
                self.registro.escribir("error", donde="estrategia", traza=traceback.format_exc())
                accion, motivo, info = accion_segura(validas), "error en la estrategia: acción segura", {}

        # N y tiempo de cada decisión: n_sim suma las simulaciones de e y de e'.
        n_sim = info.get("equity", {}).get("n", 0) + sum(r["n"] for r in info.get("equities_si_pagan", []))
        self.registro.escribir(
            "decision", id_mano=estado.id_mano, etapa=estado.etapa, cartas=texto_cartas(turno.mano),
            mesa=texto_cartas(estado.comunitarias), posicion=turno.mi_posicion,
            P=turno.P, C=turno.C, apuesta_actual=estado.apuesta_actual, saldo=turno.yo.saldo,
            s_ef_bb=round(turno.stack_efectivo_bb(), 1), rivales=len(turno.rivales),
            validas=validas, accion=accion, motivo=motivo, info=info,
            n_sim=n_sim, tiempo_s=round(time.perf_counter() - inicio, 4),
        )
        return accion

    def _estrategia(self, turno):
        """Capa 1 (capa1.py), o solo check/fold si `capa1.activa` es False (la "versión Capa 0")."""
        if not self.params["capa1"]["activa"]:
            return turno.pasar_o_retirarse(), "Capa 0: solo check/fold", {}
        return self.capa1.decidir(turno, self.mesa)
