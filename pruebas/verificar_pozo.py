#!/usr/bin/env python3
"""Pendiente 1: ¿`estado.pozo` incluye las apuestas de la calle en curso (definición de P, §0 del .tex)?

Hipótesis: dentro de una calle, pozo == (pozo al abrir la calle) + Σ apuesta_ronda de todos.
El pozo "al abrir la calle" es el del primer mensaje de esa calle, cuando todavía nadie apostó
(preflop las ciegas cuentan como apuesta_ronda, así que el punto de partida es 0).

Lee los JSONL de Bender con mensajes crudos (parámetro registro.mensajes=true, el valor por defecto
de la corrida suelta) y cuenta, por calle, cuántos estados cumplen la hipótesis, SOLO entre los que
tienen apuestas en la calle (Σ apuesta_ronda > 0).

Uso: bender/.venv/Scripts/python.exe bender/pruebas/verificar_pozo.py <bender.jsonl> [...]
"""

import json
import sys


def revisar(rutas):
    stats = {}          # etapa -> [cumplen, total_con_apuestas]
    contraejemplos = []
    for ruta in rutas:
        base = {}       # (id_mano, etapa) -> pozo al abrir la calle
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                if '"tipo":"msg"' not in linea[:80]:
                    continue
                msg = json.loads(linea)["msg"]
                e = msg.get("estado")
                if not e or msg.get("tipo") not in ("mano_inicio", "estado", "solicitar_accion"):
                    continue
                clave = (e["id_mano"], e["etapa"])
                suma = sum(j["apuesta_ronda"] for j in e["jugadores"])
                if clave not in base:
                    # Primer mensaje de la calle: sin apuestas (o preflop con ciegas) -> pozo base
                    base[clave] = e["pozo"] - suma if e["etapa"] == "preflop" else e["pozo"] - (suma if suma == 0 else 0)
                    if e["etapa"] != "preflop" and suma != 0:
                        base[clave] = None             # no vimos la apertura de la calle: no se puede juzgar
                    continue
                if base[clave] is None or suma == 0:
                    continue
                st = stats.setdefault(e["etapa"], [0, 0])
                st[1] += 1
                if e["pozo"] == base[clave] + suma:
                    st[0] += 1
                elif len(contraejemplos) < 5:
                    contraejemplos.append((e["id_mano"], e["etapa"], e["pozo"], base[clave], suma))
    return stats, contraejemplos


if __name__ == "__main__":
    stats, malos = revisar(sys.argv[1:])
    print("pozo == (pozo al abrir la calle) + Σ apuesta_ronda, solo estados con apuestas en la calle:")
    for etapa in ("preflop", "flop", "turn", "river"):
        if etapa in stats:
            ok, tot = stats[etapa]
            print(f"  {etapa:8} {ok}/{tot}")
    if malos:
        print("contraejemplos (id_mano, etapa, pozo, base, Σ apuestas):", malos)
    total = sum(t for _, t in stats.values())
    print("VEREDICTO:", "confirmado: P incluye las apuestas de la calle" if total and all(o == t for o, t in stats.values())
          else "NO concluyente / no se cumple")
