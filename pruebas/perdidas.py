#!/usr/bin/env python3
"""Revisión de manos: reconstruye cuánto ganó o perdió Bender en cada mano del historial de la
arena (guardar_historial) y lista las peores con las cartas de todos y la secuencia de acciones.

El historial no trae el neto por mano, así que se reconstruye reproduciendo las acciones:
  neto = reparto − fichas que puso (ciegas incluidas). Se valida que los netos de la mano sumen 0.

Uso:  bender/.venv/Scripts/python.exe bender/pruebas/perdidas.py <carpeta_con_manos/*.jsonl ...> [--top 15] [--yo bender]
      (acepta archivos o carpetas; con --resumen imprime además el neto por calle de la última acción)
"""

import argparse
import glob
import json
import os
import sys

PALOS, RANGOS = "cdhs", "23456789TJQKA"


def carta(c):
    return f"{RANGOS[c['rango'] - 2]}{PALOS[c['palo']]}"


STACK_INICIAL = 10_000


def neto_por_jugador(mano, stack=STACK_INICIAL):
    """{id: neto de la mano}. En el historial de la arena `jugadores[].saldo` es el saldo FINAL
    de la mano y con `reponer_stack` todos arrancan en `stack`: neto = saldo final − stack.
    Devuelve None si los netos no suman 0 (otro stack inicial u otro formato)."""
    neto = {j["id"]: j["saldo"] - stack for j in mano["jugadores"]}
    return neto if sum(neto.values()) == 0 else None


def texto_acciones(mano, yo):
    partes, etapa = [], None
    for a in mano["acciones"]:
        if a["etapa"] != etapa:
            etapa = a["etapa"]
            partes.append(f"[{etapa}]")
        t = a["accion"]
        quien = "YO" if a["id_jugador"] == yo else "rival"
        partes.append(f"{quien}:{t['tipo']}" + (f"{t['monto']}" if t.get("monto") else ""))
    return " ".join(partes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rutas", nargs="+")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--yo", default="bender")
    ap.add_argument("--resumen", action="store_true")
    args = ap.parse_args()

    archivos = []
    for r in args.rutas:
        if os.path.isdir(r):
            archivos += glob.glob(os.path.join(r, "**", "*.jsonl"), recursive=True)
        else:
            archivos += glob.glob(r)
    manos, malas = [], 0
    for ruta in archivos:
        if os.path.basename(os.path.dirname(ruta)) != "manos":
            continue
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                m = json.loads(linea)
                neto = neto_por_jugador(m)
                if neto is None or args.yo not in neto:
                    malas += 1
                    continue
                manos.append((neto[args.yo], m))
    if not manos:
        sys.exit("no se encontraron manos reconstruibles")
    total = sum(n for n, _ in manos)
    print(f"{len(manos)} manos ({malas} no reconstruibles). Neto de '{args.yo}': {total:+d} fichas = {total / 100 / len(manos) * 100:+.1f} bb/100")

    if args.resumen:
        # Dónde se pierde: por calle en la que terminó la mano y por si hubo showdown
        grupos = {}
        for n, m in manos:
            calle = m["acciones"][-1]["etapa"] if m["acciones"] else "preflop"
            clave = (calle, "showdown" if len(m["comunitarias"] or []) == 5 and m["repartos"] and len(m["privadas"]) > 1 and
                     sum(1 for j in m["jugadores"] if j["activo"]) > 1 else "sin showdown")
            g = grupos.setdefault(clave, [0, 0])
            g[0] += 1
            g[1] += n
        print("\n| termina en | manos | neto total | neto/mano |")
        print("|---|---|---|---|")
        for (calle, sd), (k, n) in sorted(grupos.items()):
            print(f"| {calle} {sd} | {k} | {n:+d} | {n / k:+.0f} |")

    print(f"\n--- las {args.top} peores manos de '{args.yo}' ---")
    for n, m in sorted(manos, key=lambda x: x[0])[:args.top]:
        priv = {i: " ".join(carta(c) for c in cs) for i, cs in m["privadas"].items()}
        yo = priv.get(args.yo, "?")
        riv = " | ".join(f"{i}: {c}" for i, c in priv.items() if i != args.yo)
        board = " ".join(carta(c) for c in (m["comunitarias"] or [])) or "-"
        print(f"{n:+6d}  yo {yo} vs {riv} | board {board} | {texto_acciones(m, args.yo)}")


if __name__ == "__main__":
    main()
