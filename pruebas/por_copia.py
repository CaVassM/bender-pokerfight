#!/usr/bin/env python3
"""P(top 6) por COPIA de cada tipo de bot en un campeonato guardado (y la de Bender), en la misma unidad.

Para cada tipo: copias por campeonato, P(top 6) POR COPIA (copias en el top 6 / copias jugadas: la unidad de Bender, que
es una sola), P(al menos una copia en el top 6) y el nº medio de copias en el top 6. Con una segunda etiqueta (`--contra`)
agrega la diferencia EMPAREJADA por semilla (IC 95 % por bootstrap) de Bender y del tipo que se pida (`--tipo novato`).

  bender/.venv/Scripts/python.exe bender/pruebas/por_copia.py camp-final-v12 --contra camp-final-u10k --tipo novato
"""

import argparse
import collections
import glob
import json
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evaluar as E  # noqa: E402


def cargar(etiqueta):
    """{semilla: {tipo: [puestos de cada copia]}}"""
    out = {}
    for f in sorted(glob.glob(os.path.join(E.SALIDAS, etiqueta, "t*", "resultado.json"))):
        res = json.load(open(f, encoding="utf-8"))
        por = collections.defaultdict(list)
        for j in res["final"]:
            por[j["tipo"]].append(j["puesto"])
        out[res["semilla"]] = dict(por)
    return out


def tabla(datos):
    n = len(datos)
    filas = []
    for t in sorted({t for d in datos.values() for t in d}):
        copias = sum(len(d.get(t, [])) for d in datos.values())
        top = sum(sum(p <= 6 for p in d.get(t, [])) for d in datos.values())
        alguna = sum(any(p <= 6 for p in d.get(t, [])) for d in datos.values())
        filas.append((t, copias // n, top / copias, alguna / n, top / n))
    return sorted(filas, key=lambda f: -f[2])


def dif(xs, ys, B=3000, semilla=3):
    d = [a - b for a, b in zip(xs, ys)]
    rng = random.Random(semilla)
    ms = sorted(statistics.fmean(rng.choices(d, k=len(d))) for _ in range(B))
    return statistics.fmean(d), ms[int(0.025 * B)], ms[int(0.975 * B)]


def por_semilla(datos, semillas, tipo):
    """fracción de copias del tipo en el top 6, por semilla"""
    return [sum(p <= 6 for p in datos[s][tipo]) / len(datos[s][tipo]) for s in semillas]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("etiqueta")
    ap.add_argument("--contra", default=None, help="etiqueta de la referencia (mismas semillas)")
    ap.add_argument("--tipo", default="novato", help="tipo cuyo P(top 6) por copia se compara además del de Bender")
    args = ap.parse_args()
    datos = cargar(args.etiqueta)
    print(f"## {args.etiqueta}: {len(datos)} campeonatos\n")
    print("| tipo | copias | P(top 6) por copia | P(alguna copia en el top 6) | copias en el top 6 (media) |")
    print("|---|---|---|---|---|")
    for t, c, p, a, m in tabla(datos):
        print(f"| {t} | {c} | {100 * p:.1f} % | {100 * a:.1f} % | {m:.2f} |")
    if args.contra:
        ref = cargar(args.contra)
        comunes = sorted(set(datos) & set(ref))
        print(f"\nDiferencia emparejada contra «{args.contra}» ({len(comunes)} semillas comunes), P(top 6) por copia, en puntos:")
        for t in ("bender", args.tipo):
            m, lo, hi = dif(por_semilla(datos, comunes, t), por_semilla(ref, comunes, t))
            print(f"- {t}: {100 * m:+.1f} (IC 95 % {100 * lo:+.1f} a {100 * hi:+.1f})")


if __name__ == "__main__":
    main()
