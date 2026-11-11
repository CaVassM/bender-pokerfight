#!/usr/bin/env python3
"""Memoria entre rondas: una "campaña" de mesas SEGUIDAS con los mismos rivales (mismos tokens), como las
rondas del torneo (los alias `id_jugador` son estables todo el campeonato).

Cada campaña = `--mesas` mesas consecutivas de `--rondas` manos con los mismos 4 rivales y el mismo Bender.
Se juegan dos versiones de cada campaña, con el mismo diseño (mismo grupo de rivales y mismo orden de
asientos en cada mesa):

  CON memoria : Bender guarda lo aprendido en disco y lo reutiliza en la mesa siguiente.
  SIN memoria : Bender empieza cada mesa sin conocer a nadie (se borra su memoria).

Se reporta la diferencia EMPAREJADA por campaña (CON − SIN) con IC 95 %, y la curva por número de mesa
(¿mejora a medida que conoce a los rivales?). Verifica además que el `id_jugador` de cada rival sale
estable por token (en modo abierto el id es el token): la memoria de una campaña tiene un archivo por
rival, no uno por mesa.

Limitación: los bots del kit reinician su propio proceso en cada mesa (la mesa cierra el socket al terminar),
así que `bandido` y `espia` no arrastran lo que aprenden. En el torneo real sí lo hacen.

Uso: bender/.venv/Scripts/python.exe bender/pruebas/campana.py --etiqueta camp-1 [--campanas 12 --mesas 10 --rondas 50]
"""

import argparse
import itertools
import json
import os
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evaluar as E  # noqa: E402


def secuencia(camp, modo, mesas, rivales, orden_por_mesa, rondas, puerto_base, dir_eval, ruta_params):
    """Las `mesas` mesas de una campaña, una tras otra. modo: 'con' o 'sin'. Devuelve la lista de bb/100 por mesa."""
    dir_camp = os.path.join(dir_eval, f"c{camp}-{modo}")
    memoria = os.path.join(dir_camp, "memoria") if modo == "con" else None
    res = []
    for t in range(mesas):
        r = E.correr_mesa(f"c{camp}", rivales, orden_por_mesa[t], rondas, puerto_base + t, os.path.join(dir_camp, f"mesa-{t}"),
                          ruta_params, memoria_dir=memoria)
        res.append(r["muestra"])
        time.sleep(0.2)
    ids = []
    if memoria and os.path.isdir(memoria):
        ids = sorted(f[:-5] for f in os.listdir(memoria) if f.endswith(".json"))
    return {"bb100": res, "ids_en_memoria": ids}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--etiqueta", required=True)
    ap.add_argument("--params", default=None)
    ap.add_argument("--campanas", type=int, default=12)
    ap.add_argument("--mesas", type=int, default=10)
    ap.add_argument("--rondas", type=int, default=50)
    ap.add_argument("--paralelo", type=int, default=8)
    ap.add_argument("--semilla", type=int, default=20261111)
    ap.add_argument("--puerto-base", type=int, default=9800)
    args = ap.parse_args()

    dir_eval = os.path.join(E.SALIDAS, f"campana-{args.etiqueta}")
    os.makedirs(dir_eval, exist_ok=True)
    ruta_params = E.archivo_params(dir_eval, args.params)
    rng = random.Random(args.semilla)
    grupos = list(itertools.combinations(E.ENTRENAMIENTO, 4))
    rng.shuffle(grupos)

    diseno = []
    for c in range(args.campanas):
        riv = list(grupos[c % len(grupos)])
        ordenes = []
        for _ in range(args.mesas):
            o = riv + ["bender"]
            rng.shuffle(o)
            ordenes.append(o)
        diseno.append((riv, ordenes))

    trabajos = [(c, modo) for c in range(args.campanas) for modo in ("con", "sin")]
    print(f"[campaña] {args.campanas} campañas × {args.mesas} mesas × {args.rondas} manos, dos versiones cada una "
          f"({len(trabajos)} secuencias, {args.paralelo} en paralelo)...", flush=True)
    with ThreadPoolExecutor(args.paralelo) as pool:
        futuros = {(c, m): pool.submit(secuencia, c, m, args.mesas, diseno[c][0], diseno[c][1], args.rondas,
                                       args.puerto_base + (2 * c + (m == "sin")) * args.mesas, dir_eval, ruta_params)
                   for c, m in trabajos}
        res = {k: f.result() for k, f in futuros.items()}

    # --- Informe ---
    validas = [c for c in range(args.campanas) if all(x is not None for m in ("con", "sin") for x in res[(c, m)]["bb100"])]
    tot = {m: [statistics.fmean(res[(c, m)]["bb100"]) for c in validas] for m in ("con", "sin")}
    difs = [a - b for a, b in zip(tot["con"], tot["sin"])]
    d, h, n = E.resumen_ic(difs)
    print(f"\n## Memoria entre rondas: {len(validas)} campañas válidas de {args.campanas}")
    print("| versión | bb/100 promedio por campaña | IC 95 % |")
    print("|---|---|---|")
    for m, nombre in (("con", "CON memoria"), ("sin", "SIN memoria")):
        mm, hh, _ = E.resumen_ic(tot[m])
        print(f"| {nombre} | {mm:+.1f} | ±{hh:.1f} |")
    print(f"\n**Diferencia emparejada (CON − SIN): {d:+.1f} ±{h:.1f} bb/100** (n={n} campañas)")

    print("\n### Por número de mesa de la campaña (bb/100, promedio de las campañas)")
    print("| mesa | " + " | ".join(str(t + 1) for t in range(args.mesas)) + " |")
    print("|---|" + "---|" * args.mesas)
    for m, nombre in (("con", "CON"), ("sin", "SIN")):
        fila = [statistics.fmean(res[(c, m)]["bb100"][t] for c in validas) for t in range(args.mesas)]
        print(f"| {nombre} | " + " | ".join(f"{x:+.0f}" for x in fila) + " |")
    primeras = [statistics.fmean(res[(c, "con")]["bb100"][t] - res[(c, "sin")]["bb100"][t] for t in range(args.mesas // 2)) for c in validas]
    ultimas = [statistics.fmean(res[(c, "con")]["bb100"][t] - res[(c, "sin")]["bb100"][t] for t in range(args.mesas // 2, args.mesas)) for c in validas]
    for nombre, v in ((f"mesas 1-{args.mesas // 2}", primeras), (f"mesas {args.mesas // 2 + 1}-{args.mesas}", ultimas)):
        dd, hh, _ = E.resumen_ic(v)
        print(f"diferencia CON − SIN en {nombre}: {dd:+.1f} ±{hh:.1f}")

    ids = sorted({i for c in validas for i in res[(c, "con")]["ids_en_memoria"]})
    por_campana = [len(res[(c, "con")]["ids_en_memoria"]) for c in validas]
    estable = all(n == 4 for n in por_campana)       # exactamente los 4 rivales (Bender no se guarda a sí mismo)
    print(f"\nId estable por token: {'SÍ' if estable else 'NO'}: la memoria de cada campaña tiene {sorted(set(por_campana))} archivos "
          f"(4 rivales esperados); ids vistos: {ids}")

    ruta = os.path.join(E.SALIDAS, "evaluaciones", f"campana-{args.etiqueta}.json")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({"etiqueta": args.etiqueta, "commit": os.environ.get("BENDER_COMMIT"), "diseno": diseno,
                   "resultados": {f"{c}-{m}": v for (c, m), v in res.items()}, "dif_emparejada": [d, h, n], "id_estable": estable}, f, indent=1)
    print(f"\n(guardado en {ruta})")


if __name__ == "__main__":
    main()
