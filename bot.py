"""Bender · el manejador de mensajes (une la conexión con la estrategia).

Paso 1 (Capa 0): la estrategia es solo check/fold, pero todo el circuito está
completo: interpreta el estado, lleva la cuenta de la mesa y de la mano,
registra cada decisión con su tiempo y N, y nunca se cae (toda decisión va en
try/except con la acción segura de respaldo, en conexion.Cliente._decidir).
Las capas 1 y 2 se enchufan en `_estrategia`.
"""

import time

from estado import (EstadoPublico, SeguimientoMesa, Turno, accion_segura, carta_de_dict,
                    texto_cartas)


class Bender:
    def __init__(self, params, registro):
        self.params = params
        self.registro = registro
        self.mi_id = None
        self.silla = -1
        self.mesa = SeguimientoMesa()

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

        if not self.mesa.tengo_cartas(estado):
            # Reconexión a mitad de mano (o mano_inicio perdido): sin cartas no
            # se puede decidir nada con criterio.
            accion, motivo = accion_segura(validas), "sin cartas de esta mano: acción segura"
            turno = Turno(estado, self.mi_id, [], validas, mensaje.get("timeout_ms", 0))
        else:
            turno = Turno(estado, self.mi_id, self.mesa.mano, validas, mensaje.get("timeout_ms", 0))
            accion, motivo = self._estrategia(turno)

        # N y tiempo de cada decisión (pedido por el equipo): n_sim se llena
        # cuando exista el Monte Carlo (paso 2); en la Capa 0 es 0.
        self.registro.escribir(
            "decision", id_mano=estado.id_mano, etapa=estado.etapa, cartas=texto_cartas(turno.mano),
            mesa=texto_cartas(estado.comunitarias), posicion=turno.mi_posicion,
            P=turno.P, C=turno.C, apuesta_actual=estado.apuesta_actual, saldo=turno.yo.saldo,
            s_ef_bb=round(turno.stack_efectivo_bb(), 1), rivales=len(turno.rivales),
            validas=validas, accion=accion, motivo=motivo,
            n_sim=0, tiempo_s=round(time.perf_counter() - inicio, 4),
        )
        return accion

    def _estrategia(self, turno):
        """Paso 1: solo check/fold. Aquí se enchufa capa1.decidir en el paso 3."""
        return turno.pasar_o_retirarse(), "Capa 0: solo check/fold"
