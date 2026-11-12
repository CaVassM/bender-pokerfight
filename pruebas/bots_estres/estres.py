#!/usr/bin/env python3
"""Bots de PRUEBA DE ESTRÉS (no son rivales para calibrar nada): juegan siempre lo mismo.

  allin   : va all-in en cada mano (cada vez que le toca)
  iguala  : siempre iguala (call; pasa si es gratis); nunca sube ni se retira
  sube_min: siempre sube el mínimo (bet/raise a la subida mínima); si no puede subir, iguala o pasa

Un bot sano tiene que ganarles con claridad. Mismo protocolo que bots/novato (conexion.py es copia de la del kit).
  python estres.py -modo allin -addr 127.0.0.1:9000 -token x
"""

import argparse
import sys

from conexion import Conexion, MesaRechazo, log


def accion(modo, mensaje, conexion):
    estado = mensaje.get("estado") or {}
    validas = mensaje.get("acciones_validas") or []
    yo = {"saldo": 0, "apuesta_ronda": 0}
    for j in estado.get("jugadores", []):
        if j.get("id") == conexion.id_jugador:
            yo = j
            break

    def pagar():
        for t in ("call", "check"):
            if t in validas:
                return {"tipo": t}
        return {"tipo": "allin"} if "allin" in validas else {"tipo": "fold"}

    if modo == "allin":
        return {"tipo": "allin"} if "allin" in validas else pagar()
    if modo == "iguala":
        return pagar()
    # sube_min
    actual = estado.get("apuesta_actual", 0)
    tipo = "bet" if actual <= yo.get("apuesta_ronda", 0) else "raise"
    total = actual + estado.get("subida_minima", 0)
    if tipo in validas:
        if total >= yo.get("saldo", 0) + yo.get("apuesta_ronda", 0):
            return {"tipo": "allin"} if "allin" in validas else pagar()
        return {"tipo": tipo, "monto": int(total)}
    return pagar()


def jugar(conexion, modo):
    while True:
        try:
            m = conexion.recibir()
        except OSError:
            return False
        if m is None:
            return True
        if m.get("tipo") == "solicitar_accion":
            try:
                conexion.responder(m.get("estado") or {}, accion(modo, m, conexion))
            except OSError:
                return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-modo", choices=["allin", "iguala", "sube_min"], required=True)
    ap.add_argument("-addr", default="localhost:9000")
    ap.add_argument("-token", default="estres")
    ap.add_argument("-silencioso", action="store_true")
    a = ap.parse_args()
    c = Conexion(a.addr, a.token)
    try:
        c.conectar()
    except (MesaRechazo, ConnectionError) as e:
        log(f"estres[{a.modo}]: {e}")
        sys.exit(1)
    for intento in range(6):
        if jugar(c, a.modo):
            return
        c.cerrar()
        try:
            c.conectar(intentos=10, espera_s=0.5)
        except (MesaRechazo, ConnectionError):
            break
    sys.exit(1)


if __name__ == "__main__":
    main()
