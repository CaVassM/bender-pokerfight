#!/usr/bin/env python3
"""Tabla final de comparar_riesgo.py: una fila por configuración, con las diferencias EMPAREJADAS contra `v1`.

Campeonatos (camp-riesgo-<cfg>.json): P(top 6), P(sobrevivir las 10 rondas), puesto medio, quiebra por mesa de Bender en el
campeonato. Mesas de 5 a 10 000 fichas (riesgo-mesas-<cfg>.json): tasa de quiebra por mesa y bb/100.
Las diferencias son emparejadas (mismas semillas: mismo sorteo y mismas cartas en la primera ronda; mesas con el mismo
plan de rivales y asientos); el IC 95 % sale de un bootstrap sobre los pares.

  bender/.venv/Scripts/python.exe bender/pruebas/resumen_riesgo.py
"""

import json
import math
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evaluar as E  # noqa: E402

ORDEN = ["v1", "cal", "calpre", "u5k", "u5k-calpre", "u10k", "u10k-calpre", "u20k", "u20k-calpre", "u40k", "u40k-calpre", "u5k-cal", "u10k-cal", "u20k-cal", "u40k-cal"]
EV = os.path.join(E.SALIDAS, "evaluaciones")


def cargar(nombre):
    ruta = os.path.join(EV, nombre + ".json")
    return json.load(open(ruta, encoding="utf-8")) if os.path.exists(ruta) else None


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def dif(xs, ys, B=3000, semilla=3):
    """media(xs − ys) emparejada y su IC 95 % por bootstrap; None si hay pocos pares."""
    d = [a - b for a, b in zip(xs, ys)]
    if len(d) < 10:
        return None
    rng = random.Random(semilla)
    ms = sorted(statistics.fmean(rng.choices(d, k=len(d))) for _ in range(B))
    return statistics.fmean(d), ms[int(0.025 * B)], ms[int(0.975 * B)]


def pts(v):
    return "—" if v is None else f"{100 * v[0]:+.1f} ({100 * v[1]:+.1f} a {100 * v[2]:+.1f})"


def num(v, d=1):
    return "—" if v is None else f"{v[0]:+.{d}f} ({v[1]:+.{d}f} a {v[2]:+.{d}f})"


def alinear_camp(c, ref):
    """Indicadores de los campeonatos con semilla común."""
    sa, sb = c["indicadores"]["semillas"], ref["indicadores"]["semillas"]
    comunes = [s for s in sa if s in set(sb)]
    ia, ib = {s: i for i, s in enumerate(sa)}, {s: i for i, s in enumerate(sb)}
    return comunes, ia, ib


def main():
    ref_c, ref_m = cargar("camp-riesgo-v1"), cargar("riesgo-mesas-v1")
    print("## Campeonato (10 rondas, mesas de 5-6, fichas que se arrastran, eliminación en 0; campo: 24 bots del kit de entrenamiento + Bender)\n")
    print("| config | campeonatos | P(top 6) | Δ vs v1 (pts) | P(sobrevivir 10 rondas) | Δ vs v1 (pts) | puesto medio | Δ vs v1 | quiebra por mesa (Bender) | bb/100 en el campeonato |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for cfg in ORDEN:
        c = cargar("camp-riesgo-" + cfg)
        if not c:
            continue
        top, surv, ps = c["p_top6"], c["p_sobrevivir"], c["puesto_medio"]
        extra = ["—", "—", "—"]
        if ref_c and cfg != "v1":
            comunes, ia, ib = alinear_camp(c, ref_c)
            extra = []
            for clave in ("top6", "sobrevive", "puesto"):
                xs = [c["indicadores"][clave][ia[s]] for s in comunes]
                ys = [ref_c["indicadores"][clave][ib[s]] for s in comunes]
                d = dif(xs, ys)
                extra.append(num(d, 2) if clave == "puesto" else pts(d))
        b = c["por_tipo_mesa"]["bender"]["todas"]
        bb = c["bb100_bender"]
        print(f"| {cfg} | {c['torneos']} | {100 * top[0]:.1f} % ({100 * top[1]:.0f}-{100 * top[2]:.0f}) | {extra[0]} | "
              f"{100 * surv[0]:.1f} % ({100 * surv[1]:.0f}-{100 * surv[2]:.0f}) | {extra[1]} | {ps:.1f} | {extra[2]} | "
              f"{100 * b['tasa_quiebra']:.1f} % ({b['mesas']}) | {bb[0]:+.0f} ±{bb[1]:.0f} |")
    print("\n## Mesas de 5 a 10 000 fichas, 50 manos (rivales de entrenamiento)\n")
    print("| config | mesas | quiebra por mesa | Δ vs v1 (pts) | bb/100 | Δ vs v1 (bb/100) | fichas finales: mediana / media |")
    print("|---|---|---|---|---|---|---|")
    for cfg in ORDEN:
        m = cargar("riesgo-mesas-" + cfg)
        if not m:
            continue
        det = {t["i"]: t for t in m["mesa"]["detalle"] if t["final"] is not None}
        fin = [t["final"] for t in det.values()]
        k = sum(1 for f in fin if f == 0)
        lo, hi = wilson(k, len(fin))
        mu, h, n = E.resumen_ic([t["muestra"] for t in det.values()])
        d_q = d_b = None
        if ref_m and cfg != "v1":
            rd = {t["i"]: t for t in ref_m["mesa"]["detalle"] if t["final"] is not None}
            comunes = sorted(set(det) & set(rd))
            d_q = dif([1.0 if det[i]["final"] == 0 else 0.0 for i in comunes], [1.0 if rd[i]["final"] == 0 else 0.0 for i in comunes])
            d_b = dif([det[i]["muestra"] for i in comunes], [rd[i]["muestra"] for i in comunes])
        print(f"| {cfg} | {len(fin)} | {100 * k / len(fin):.1f} % ({100 * lo:.0f}-{100 * hi:.0f}) | {pts(d_q)} | {mu:+.1f} ±{h:.1f} | {num(d_b)} | "
              f"{statistics.median(fin):,.0f} / {statistics.fmean(fin):,.0f} |")


if __name__ == "__main__":
    main()
