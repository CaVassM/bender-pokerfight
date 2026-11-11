#!/usr/bin/env python3
"""Complemento de analizar_quiebras.py: ¿de dónde sale el beneficio y cuánto riesgo de quiebra compra cada tipo de decisión?

Para TODAS las decisiones que comprometen >= 50 % del stack (no solo las que acaban en pérdida grande) mide, por tipo,
frecuencia, beneficio real (de la decisión al final de la mano), tasa de quiebra por decisión y el EV que se perdería
si las decisiones "dudosas" (margen de EV pequeño frente a la mejor alternativa) se cambiaran por esa alternativa.
No modifica nada de Bender: solo lee los logs de una corrida (--mensajes).

  python bender/pruebas/riesgo_ev.py --etiqueta noche-600
"""

import argparse
import json
import math
import os
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analizar_quiebras as A  # noqa: E402
import evaluar as E  # noqa: E402

BB = E.BB


def cubeta_margen(m):
    if m is None:
        return "sin margen"
    if m < 0.02:
        return "< 2 % del stack"
    if m < 0.05:
        return "2-5 %"
    if m < 0.10:
        return "5-10 %"
    return "≥ 10 %"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--etiqueta", required=True)
    args = ap.parse_args()
    res = json.load(open(os.path.join(E.SALIDAS, "evaluaciones", f"{args.etiqueta}.json"), encoding="utf-8"))
    dir_eval = os.path.join(E.SALIDAS, f"eval-{args.etiqueta}")
    validas = [t for t in res["mesa"]["detalle"] if t["final"] is not None]

    filas, manos_total, benef_total, quiebras_total = [], 0, 0.0, 0
    for t in validas:
        manos = A.leer_mesa(os.path.join(dir_eval, f"mesa-{t['i']}", "bender.jsonl"), t["i"], t["final"])
        manos_total += len(manos)
        for m in manos:
            benef_total += (m["despues"] - m["antes"]) / BB
            if m["despues"] == 0 and m["antes"] > 0:
                quiebras_total += 1
            ds, invs = A.inversiones(m)
            if not ds:
                continue
            j = max(range(len(ds)), key=lambda q: (invs[q], q))
            d = A.describir(m, ds[j], invs[j])
            if d["saldo"] and d["inversion"] >= 0.5 * d["saldo"]:
                d["cat"] = A.categoria(d, True)
                d["delta_bb"] = (m["despues"] - ds[j]["saldo"]) / BB
                d["quiebra"] = m["despues"] == 0
                d["perdida_total_pct"] = (m["antes"] - m["despues"]) / m["antes"]
                d["antes"] = m["antes"]
                d["mesa_i"] = t["i"]
                filas.append(d)

    n_mesas = len(validas)
    print(f"## Riesgo y EV por tipo de decisión «{args.etiqueta}» ({n_mesas} mesas, {manos_total} manos de Bender, {quiebras_total} quiebras)")
    print(f"Beneficio total de Bender en estas manos: {benef_total:+,.0f} bb = {100 * benef_total / manos_total:+.1f} bb/100 manos "
          f"(el IC de la corrida está en el JSON de evaluar). Decisiones que comprometen ≥ 50 % del stack: {len(filas)} "
          f"({len(filas) / n_mesas:.1f} por mesa).\n")

    por_cat = defaultdict(list)
    for f in filas:
        por_cat[f["cat"]].append(f)
    print("### Beneficio y quiebra por tipo de decisión que compromete ≥ 50 % del stack")
    print("(beneficio = de la decisión al final de la mano; no incluye lo invertido antes en esa mano)\n")
    print("| tipo | decisiones | por mesa | beneficio real total (bb) | bb/100 manos que aporta | por decisión (bb) | quiebras | % quiebra por decisión | % de las quiebras |\n|---|---|---|---|---|---|---|---|---|")
    for cat, fs in sorted(por_cat.items(), key=lambda x: -len(x[1])):
        tot = sum(f["delta_bb"] for f in fs)
        q = sum(1 for f in fs if f["quiebra"])
        print(f"| {cat} | {len(fs)} | {len(fs) / n_mesas:.2f} | {tot:+,.0f} | {100 * tot / manos_total:+.1f} | {tot / len(fs):+.1f} | {q} | {100 * q / len(fs):.1f} % | {100 * q / max(1, quiebras_total):.0f} % |")
    print(f"| (total mostrado) | {len(filas)} | | {sum(f['delta_bb'] for f in filas):+,.0f} | {100 * sum(f['delta_bb'] for f in filas) / manos_total:+.1f} | | {sum(1 for f in filas if f['quiebra'])} | | {100 * sum(1 for f in filas if f['quiebra']) / max(1, quiebras_total):.0f} % |")

    # --- all-in propio profundo: por margen, calle, profundidad, rivales
    pro = [f for f in filas if f["cat"] == "all-in propio, modo profundo"]
    print(f"\n### All-in propio en modo profundo ({len(pro)} decisiones): cómo se reparte el riesgo")

    def tabla(titulo, clave, orden=None):
        g = defaultdict(list)
        for f in pro:
            g[clave(f)].append(f)
        print(f"\n**Por {titulo}**\n")
        print("| grupo | n | EV previsto (bb) | resultado real (bb) ±EE | % quiebra por decisión | e' media | f mediana |\n|---|---|---|---|---|---|---|")
        for k in (orden or sorted(g)):
            fs = g.get(k)
            if not fs:
                continue
            real = [f["delta_bb"] for f in fs]
            ee = statistics.stdev(real) / math.sqrt(len(real)) if len(real) > 1 else float("nan")
            evp = [f["ev_elegida"] / BB for f in fs if f["ev_elegida"] is not None]
            ep = [f["e_prima"] for f in fs if f["e_prima"] is not None]
            ff = [f["f"] for f in fs if f["f"] is not None]
            print(f"| {k} | {len(fs)} | {statistics.mean(evp):+.1f} | {statistics.mean(real):+.1f} ±{ee:.1f} | "
                  f"{100 * sum(1 for f in fs if f['quiebra']) / len(fs):.1f} % | {statistics.mean(ep) if ep else float('nan'):.2f} | {statistics.median(ff) if ff else float('nan'):.2f} |")

    tabla("margen de EV frente a la mejor alternativa", lambda f: cubeta_margen(f["margen_ev"]),
          ["< 2 % del stack", "2-5 %", "5-10 %", "≥ 10 % ", "≥ 10 %", "sin margen"])
    tabla("calle", lambda f: f["etapa"], ["preflop", "flop", "turn", "river"])
    tabla("stack efectivo", lambda f: ("< 50 bb" if (f["s_ef_bb"] or 0) < 50 else "50-100 bb" if f["s_ef_bb"] < 100 else "≥ 100 bb"),
          ["< 50 bb", "50-100 bb", "≥ 100 bb"])
    tabla("rivales en la decisión", lambda f: "1 rival" if (f["n_rivales_decision"] or 0) <= 1 else "2 rivales" if f["n_rivales_decision"] == 2 else "3-4 rivales",
          ["1 rival", "2 rivales", "3-4 rivales"])
    tabla("probabilidad de que le paguen (e' cuando pagan)", lambda f: "sin e'" if f["e_prima"] is None else ("e' < 0,5" if f["e_prima"] < 0.5 else "0,5 ≤ e' < 0,6" if f["e_prima"] < 0.6 else "0,6 ≤ e' < 0,7" if f["e_prima"] < 0.7 else "e' ≥ 0,7"),
          ["e' < 0,5", "0,5 ≤ e' < 0,6", "0,6 ≤ e' < 0,7", "e' ≥ 0,7"])

    # --- qué costaría una regla "si el margen es pequeño, no vayas all-in": cota
    print("\n### Cota de lo que costaría (en EV) y de lo que evitaría (en quiebras) un umbral de margen")
    print("Regla hipotética: si EV(all-in) − EV(mejor alternativa) < umbral, jugar la alternativa. Coste = Σ margen·saldo (EV que se deja); "
          "quiebras evitables = COTA SUPERIOR (supone que la alternativa nunca acaba en quiebra, cosa falsa: una apuesta de bote también se puede perder entera después).\n")
    print("| umbral (% del stack) | all-in afectados | % de los all-in profundos | EV cedido (bb/100 manos) | quiebras de all-in profundo que caen en ellos | cota de quiebras evitables (% de las 125) |\n|---|---|---|---|---|---|")
    for u in (0.02, 0.05, 0.10):
        sel = [f for f in pro if f["margen_ev"] is not None and f["margen_ev"] < u]
        coste = sum(f["margen_ev"] * f["saldo"] / BB for f in sel)
        q = sum(1 for f in sel if f["quiebra"])
        print(f"| {int(u * 100)} % | {len(sel)} | {100 * len(sel) / len(pro):.0f} % | {100 * coste / manos_total:.1f} | {q} | {100 * q / max(1, quiebras_total):.0f} % |")

    # --- cuántas quiebras no se explican por un solo compromiso
    q_filas = [f for f in filas if f["quiebra"]]
    print(f"\nQuiebras cuya decisión decisiva compromete ≥ 50 % del stack: {len(q_filas)} de {quiebras_total} "
          f"({100 * len(q_filas) / max(1, quiebras_total):.0f} %); el resto son manos de desgaste / ciegas con stack mínimo.")
    antes = [f["antes"] / BB for f in q_filas]
    print(f"Stack al empezar esas manos (bb): p25 {A.percentil(antes, 25):.0f} | mediana {A.percentil(antes, 50):.0f} | p75 {A.percentil(antes, 75):.0f}")

    # --- ¿cuántas quiebras vienen de manos en que Bender partía con ventaja?
    fav = [f for f in q_filas if f["e_prima"] is not None]
    if fav:
        print(f"De esas quiebras, con e' (equity si le pagan) disponible ({len(fav)}): e' ≥ 0,5 en {100 * sum(1 for f in fav if f['e_prima'] >= 0.5) / len(fav):.0f} % "
              f"(media {statistics.mean(f['e_prima'] for f in fav):.2f}), es decir, casi todas son «favorito que pierde», no «underdog forzado».")


if __name__ == "__main__":
    main()
