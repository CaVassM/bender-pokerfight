#!/usr/bin/env python3
"""Tasa de quiebra por mesa de CADA bot (y de Bender) en una corrida de mesas de 5 (evaluar.py --solo-mesa).

Lee el resumen que imprime la mesa al terminar (`#N <id> <fichas>`) de cada eval-<etiqueta>/mesa-<i>/mesa.out: no necesita
logs de Bender. Un bot "quiebra" si termina la mesa (50 manos, 10 000 fichas iniciales) con 0 fichas. Los rivales se
conectan con el token k-<bot>; Bender, con bender-<i>.

  bender/.venv/Scripts/python.exe bender/pruebas/quiebra_por_bot.py --etiqueta noche-600
"""

import argparse
import glob
import math
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evaluar as E  # noqa: E402

LINEA = re.compile(r"^\s*#(\d+)\s+(\S+)\s+(\d+)\s+fichas")


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--etiqueta", required=True)
    args = ap.parse_args()
    datos = {}
    for ruta in glob.glob(os.path.join(E.SALIDAS, f"eval-{args.etiqueta}", "mesa-*", "mesa.out")):
        texto = open(ruta, encoding="utf-8", errors="replace").read()
        if "partida terminada" not in texto:
            continue
        for linea in texto.splitlines():
            m = LINEA.match(linea)
            if not m:
                continue
            jugador = "bender" if m.group(2).startswith("bender") else m.group(2).replace("k-", "")
            datos.setdefault(jugador, []).append(int(m.group(3)))
    print(f"## Quiebra por mesa de cada bot «{args.etiqueta}» (mesas de 5, 50 manos, 10 000 fichas iniciales)\n")
    print("| bot | mesas | quiebras | tasa | IC 95 % | fichas finales: mediana | media |\n|---|---|---|---|---|---|---|")
    for j in sorted(datos, key=lambda j: (j != "bender", j)):
        fs = datos[j]
        k = sum(1 for f in fs if f == 0)
        lo, hi = wilson(k, len(fs))
        print(f"| {'**bender**' if j == 'bender' else j} | {len(fs)} | {k} | {100 * k / len(fs):.1f} % | {100 * lo:.0f}-{100 * hi:.0f} % | "
              f"{statistics.median(fs):,.0f} | {statistics.fmean(fs):,.0f} |")


if __name__ == "__main__":
    main()
