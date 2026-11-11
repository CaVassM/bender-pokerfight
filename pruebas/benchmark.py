#!/usr/bin/env python3
"""Benchmark del motor (paso 2).

  A) Evaluaciones de 7 cartas por segundo (C directo, envoltorio público, cartas.evaluar).
  B) Simulaciones por segundo del Monte Carlo con 1, 2 y 4 rivales (preflop y flop), y
     cuántas caben en 2 s.
  C) Distribución del tiempo por decisión (mediana y p95) con el reloj adaptativo de §1.2,
     en spots aleatorios: calle, nº de rivales, rangos y umbrales (e_min, 0,25, 0,50) al azar.

Uso:  bender/.venv/Scripts/python.exe bender/pruebas/benchmark.py [--decisiones 400]
"""

import argparse
import json
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cartas as C          # noqa: E402
import rangos as R          # noqa: E402
from equity import estimar, t_max_de_reloj   # noqa: E402
from params import cargar_params             # noqa: E402

RELOJ = cargar_params()["reloj"]


def percentil(valores, p):
    v = sorted(valores)
    return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]


def bench_evaluador():
    from phevaluator import evaluate_cards
    rng = random.Random(1)
    manos = [rng.sample(range(52), 7) for _ in range(300_000)]
    out = {}
    for nombre, f in (("C directo (_pheval.evaluate_7cards)", lambda m: C.evaluar7(*m)),
                      ("cartas.evaluar (despacha por largo)", lambda m: C.evaluar(m)),
                      ("phevaluator.evaluate_cards (público)", lambda m: evaluate_cards(*m))):
        t = time.perf_counter()
        for m in manos:
            f(m)
        out[nombre] = len(manos) / (time.perf_counter() - t)
    return out


def bench_simulaciones():
    rng = random.Random(5)
    out = {}
    for calle, board_txt in (("preflop", ""), ("flop", "Jd 7c 2s"), ("turn", "Jd 7c 2s 9h"), ("river", "Jd 7c 2s 9h Kd")):
        board = C.cartas_de_texto(board_txt) if board_txt else []
        mano = C.cartas_de_texto("As Ts")
        muertas = C.mascara(mano + board)
        for n_riv in (1, 2, 4):
            rivales = [R.rango_alazar(muertas) for _ in range(n_riv)]
            r = estimar(mano, board, rivales, n_fijo=40_000, rng=rng)
            sps = r.n / r.tiempo_s
            out[f"{calle} / {n_riv} rival{'es' if n_riv > 1 else ''}"] = {"sim_por_s": sps, "caben_en_2s": int(sps * 2)}
    return out


def spot_aleatorio(rng, rangos_pre):
    """Un spot de decisión: mano, board, rivales con rangos, umbrales."""
    calle = rng.choices(["preflop", "flop", "turn", "river"], weights=[35, 30, 20, 15])[0]
    cartas = rng.sample(range(52), 2 + {"preflop": 0, "flop": 3, "turn": 4, "river": 5}[calle])
    mano, board = cartas[:2], cartas[2:]
    n_riv = rng.choices([1, 2, 3, 4], weights=[30, 30, 25, 15])[0]
    rivales = [rangos_pre[rng.choice(list(rangos_pre))] for _ in range(n_riv)]
    umbrales = [0.25, 0.50]
    if rng.random() < 0.5:                         # hay una apuesta que igualar: e_min = x / (1 + 2x)
        x = rng.choice([0.33, 0.5, 0.75, 1.0])
        umbrales.append(x / (1 + 2 * x))
    return mano, board, rivales, umbrales, n_riv, calle


def bench_decisiones(n_decisiones, seg_por_mano):
    rng = random.Random(11)
    rangos_pre = {p: R.rango_top(p) for p in (15, 25, 40, 100)}
    filas = []
    for i in range(n_decisiones):
        mano, board, rivales, umbrales, n_riv, calle = spot_aleatorio(rng, rangos_pre)
        manos_jugadas = rng.randrange(0, 50)
        segundos = manos_jugadas * seg_por_mano
        r = estimar(mano, board, rivales, RELOJ, umbrales=umbrales, manos_jugadas=manos_jugadas,
                    segundos_mesa=segundos, rng=rng)
        filas.append({"t": r.tiempo_s, "n": r.n, "parada": r.parada, "rivales": n_riv, "calle": calle,
                      "t_max": r.t_max, "imposible": r.imposible})
    return filas


def resumen(filas, titulo):
    ts = [f["t"] for f in filas]
    ns = [f["n"] for f in filas]
    print(f"\n### {titulo}  ({len(filas)} decisiones)")
    print(f"tiempo por decisión: mediana {statistics.median(ts)*1000:.0f} ms | p95 {percentil(ts, 95)*1000:.0f} ms | "
          f"p99 {percentil(ts, 99)*1000:.0f} ms | máx {max(ts)*1000:.0f} ms | media {statistics.mean(ts)*1000:.0f} ms")
    print(f"N por decisión:      mediana {statistics.median(ns):.0f} | p95 {percentil(ns, 95):.0f}")
    paradas = {}
    for f in filas:
        paradas[f["parada"]] = paradas.get(f["parada"], 0) + 1
    print("motivo de parada:    " + ", ".join(f"{k} {v / len(filas):.0%}" for k, v in sorted(paradas.items())))
    print("| rivales | decisiones | mediana ms | p95 ms | mediana N |")
    print("|---|---|---|---|---|")
    for n_riv in (1, 2, 3, 4):
        sub = [f for f in filas if f["rivales"] == n_riv]
        if sub:
            t = [f["t"] for f in sub]
            print(f"| {n_riv} | {len(sub)} | {statistics.median(t)*1000:.0f} | {percentil(t, 95)*1000:.0f} | "
                  f"{statistics.median([f['n'] for f in sub]):.0f} |")
    print("| calle | decisiones | mediana ms | p95 ms | mediana N |")
    print("|---|---|---|---|---|")
    for calle in ("preflop", "flop", "turn", "river"):
        sub = [f for f in filas if f["calle"] == calle]
        if sub:
            t = [f["t"] for f in sub]
            print(f"| {calle} | {len(sub)} | {statistics.median(t)*1000:.0f} | {percentil(t, 95)*1000:.0f} | "
                  f"{statistics.median([f['n'] for f in sub]):.0f} |")
    return {"mediana_ms": statistics.median(ts) * 1000, "p95_ms": percentil(ts, 95) * 1000,
            "mediana_n": statistics.median(ns), "p95_n": percentil(ns, 95)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decisiones", type=int, default=400)
    ap.add_argument("--eps-obj", type=float, default=None, help="sobreescribe ε_obj (por defecto el de params.py)")
    ap.add_argument("--n-min", type=int, default=None, help="sobreescribe N_min (por defecto el de params.py)")
    ap.add_argument("--solo-decisiones", action="store_true", help="salta los bloques A y B")
    args = ap.parse_args()
    if args.eps_obj is not None:
        RELOJ["eps_obj"] = args.eps_obj
    if args.n_min is not None:
        RELOJ["n_min"] = args.n_min
    print(f"reloj: N_min={RELOJ['n_min']} ε_obj={RELOJ['eps_obj']} k={RELOJ['k']} T_tope={RELOJ['t_tope']} η={RELOJ['eta']}")
    out = {}
    if args.solo_decisiones:
        out["decisiones_al_dia"] = resumen(bench_decisiones(args.decisiones, 7.2), "Mesa al día (7,2 s por mano en promedio)")
        return

    print("## A) Evaluador (evaluaciones de 7 cartas por segundo)")
    out["evaluador"] = bench_evaluador()
    for k, v in out["evaluador"].items():
        print(f"  {k:42} {v:>12,.0f}/s")

    print("\n## B) Simulaciones por segundo del Monte Carlo (rivales con mano al azar, 40 000 sim)")
    out["simulaciones"] = bench_simulaciones()
    print("| spot | sim/s | caben en 2 s |")
    print("|---|---|---|")
    for k, v in out["simulaciones"].items():
        print(f"| {k} | {v['sim_por_s']:,.0f} | {v['caben_en_2s']:,} |")

    print(f"\n## C) Tiempo por decisión con el reloj adaptativo (T_max = min({RELOJ['t_tope']} s, η·T_rest/D_rest))")
    print(f"T_max de referencia: mesa al día (7,2 s/mano) -> {t_max_de_reloj(RELOJ, 25, 25*7.2):.2f} s; "
          f"mesa atrasada (9 s/mano, mano 25) -> {t_max_de_reloj(RELOJ, 25, 25*9.0):.2f} s")
    out["decisiones_al_dia"] = resumen(bench_decisiones(args.decisiones, 7.2), "Mesa al día (7,2 s por mano en promedio)")
    out["decisiones_atrasada"] = resumen(bench_decisiones(args.decisiones, 9.0), "Mesa atrasada (9 s por mano: el reloj aprieta)")

    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "salidas", "benchmark.json")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(f"\n(resultados en {ruta})")


if __name__ == "__main__":
    main()
