#!/usr/bin/env python3
"""Simulador de la FINAL (pedido del usuario, 2026-11-17): una mesa de 6, 10 000 fichas cada uno, ciegas 50/100, hasta que
quede uno o hasta N manos (por defecto 400: el ritmo de bots reales no está medido). Gana el último en pie o, si se acaba el
tope de manos, el de más fichas.

Rivales (los mismos 5 toda la final): bender_agresivo, bender_v1, novato, darwin y bandido. Bender (el sujeto) se evalúa con
cinco configuraciones, EMPAREJADAS por semilla (mismas cartas, mismas sillas, mismos alias; las sillas rotan al azar de una
semilla a otra):

  a  v1.4-final     (los defaults: K = 6000)
  b  K = 20 000
  c  K = 40 000
  d  utilidad apagada (EV puro)
  e  bandido online (UCB con descuento) eligiendo entre a, b y d; el valor se aprende por rival activo (los mismos 5 toda la final)

Reutiliza el conductor Go de la clasificatoria (bin/campeonato.exe) con 1 ronda, 1 mesa de 6 y `manos = N`.
darwin y novato son de RESERVA: esta es la evaluación final que el usuario pidió explícitamente.

  bender/.venv/Scripts/python.exe bender/pruebas/evaluar_fijo.py --script final_sim.py -- --nombre fin1 --n 400
"""

import argparse
import json
import math
import os
import random
import shutil
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campeonato as CAMP  # noqa: E402
import evaluar as E  # noqa: E402

SEMILLA = 18_000_000
RIVALES = [("bender_agresivo", 1), ("bender_v1", 1), ("novato", 1), ("darwin", 1), ("bandido", 1)]
K_ARM = {"riesgo": {"K": 20_000}}
EV_ARM = {"riesgo": {"utilidad": False}}
CONFIGS = {
    "a": {"nombre": "a · v1.4-final (K = 6000)", "variante": {}},
    "b": {"nombre": "b · K = 20 000", "variante": {"riesgo": {"K": 20_000}}},
    "c": {"nombre": "c · K = 40 000", "variante": {"riesgo": {"K": 40_000}}},
    "d": {"nombre": "d · utilidad apagada (EV puro)", "variante": {"riesgo": {"utilidad": False}}},
    "e": {"nombre": "e · bandido UCB entre a, b y d",
          "variante": {"bandido": {"activo": True, "selector": "ucb", "orden": ["a", "b", "d"], "brazo_inicial": "a",
                                   "brazos": {"a": {}, "b": K_ARM, "d": EV_ARM}}}},
}
BB = 100


def correr_final(semilla, cid, dir_base, manos, max_mesa_s):
    dir_t = os.path.join(dir_base, cid, f"t{semilla}")
    ruta_res = os.path.join(dir_t, "resultado.json")
    ruta_sum = os.path.join(dir_t, "resumen.json")
    if os.path.exists(ruta_sum):                                  # reanudable
        return json.load(open(ruta_sum, encoding="utf-8"))
    os.makedirs(dir_t, exist_ok=True)
    p = json.loads(json.dumps(CONFIGS[cid]["variante"]))
    p.setdefault("rivales", {})["dir"] = os.path.join(dir_t, "rivales")      # la memoria se acumula en la mesa
    p.setdefault("registro", {})["mensajes"] = False
    ruta_p = os.path.join(dir_t, "params-bender.json")
    json.dump(p, open(ruta_p, "w", encoding="utf-8"))
    cfg = {"semilla": semilla, "rondas": 1, "manos": manos, "ciega_chica": 50, "ciega_grande": 100, "stack": CAMP.STACK,
           "timeout_ms": 5000, "max_mesa_s": max_mesa_s, "participantes": CAMP.armar(semilla, RIVALES, ruta_p, dir_t)}
    ruta_cfg = os.path.join(dir_t, "torneo.json")
    json.dump(cfg, open(ruta_cfg, "w", encoding="utf-8"))
    t0 = time.time()
    r = subprocess.run([os.path.join(E.BIN, "campeonato" + E.EXE), "-config", ruta_cfg, "-salida", ruta_res], cwd=E.RAIZ,
                       capture_output=True, text=True, timeout=max_mesa_s + 600)
    dt = time.time() - t0
    if r.returncode != 0 or not os.path.exists(ruta_res):
        return {"semilla": semilla, "cid": cid, "error": f"conductor: {r.stderr[-300:]}"}
    res = json.load(open(ruta_res, encoding="utf-8"))
    mesa = res["rondas"][0][0]
    if mesa.get("error"):
        out = {"semilla": semilla, "cid": cid, "error": mesa["error"]}
    else:
        yo = next(f for f in res["final"] if f["tipo"] == "bender")
        vivos = sum(1 for f in res["final"] if f["fichas"] > 0)
        out = {"semilla": semilla, "cid": cid, "puesto": yo["puesto"], "fichas": yo["fichas"], "manos": mesa["manos_jugadas"],
               "vivos": vivos, "tope": vivos > 1, "dur_s": round(dt, 1),
               "ganador": next(f["tipo"] for f in res["final"] if f["puesto"] == 1),
               "puestos": {f["tipo"] if f["tipo"] != "bender" else "bender": f["puesto"] for f in res["final"]},
               "timeouts": {j["tipo"]: j["timeouts"] for j in mesa["jugadores"]}}
        if cid == "e":                                            # cuánto usó cada brazo (log del sujeto)
            uso = {}
            try:
                for linea in open(os.path.join(dir_t, "bender.jsonl"), encoding="utf-8"):
                    if '"tipo":"bandido"' in linea.replace(" ", "")[:40] or '"tipo": "bandido"' in linea[:60]:
                        b = json.loads(linea).get("brazo")
                        uso[b] = uso.get(b, 0) + 1
            except OSError:
                pass
            out["brazos"] = uso
    json.dump(out, open(ruta_sum, "w", encoding="utf-8"))
    for nombre in os.listdir(dir_t):                              # los logs de 5 procesos por final pesan decenas de MB
        if nombre.endswith(".jsonl") or nombre.startswith("rivales"):
            ruta = os.path.join(dir_t, nombre)
            shutil.rmtree(ruta, ignore_errors=True) if os.path.isdir(ruta) else os.remove(ruta)
    return out


# ------------------------------------------------------------------ estadística
def wilson(k, n, z=1.96):
    return CAMP.wilson(k, n, z)


def bootstrap_dif(xs, ys, B=4000, z=0.025, rng=None):
    """Media de (xs - ys) emparejada y su IC por percentiles (z = cola de cada lado)."""
    rng = rng or random.Random(12345)
    d = [a - b for a, b in zip(xs, ys)]
    n = len(d)
    ms = sorted(statistics.fmean(rng.choices(d, k=n)) for _ in range(B))
    return statistics.fmean(d), ms[int(z * B)], ms[min(B - 1, int((1 - z) * B))]


def indicadores(regs):
    return {"gana": [1.0 if r["puesto"] == 1 else 0.0 for r in regs], "top2": [1.0 if r["puesto"] <= 2 else 0.0 for r in regs],
            "top3": [1.0 if r["puesto"] <= 3 else 0.0 for r in regs], "puesto": [float(r["puesto"]) for r in regs]}


def informe(directorio, datos, semillas, args):
    """datos[cid][semilla] = registro; solo cuentan las semillas válidas en TODAS las configuraciones (emparejado)."""
    ids = [c for c in CONFIGS if c in datos]
    validas = [s for s in semillas if all(s in datos[c] and "puesto" in datos[c][s] for c in ids)]
    descartadas = len(semillas) - len(validas)
    L = [f"# Final simulada (commit {os.environ.get('BENDER_COMMIT')}): {len(validas)} finales emparejadas por configuración\n",
         f"Mesa de 6 (Bender + {', '.join(n for n, _ in RIVALES)}), 10 000 fichas, ciegas 50/100, hasta que quede uno o {args.manos} manos "
         f"(gana el de más fichas). Semillas {SEMILLA}+i. Azar puro: P(ganar) = 16,7 %. Finales descartadas (error del conductor en alguna "
         f"configuración): {descartadas}.\n",
         "| configuración | P(ganar) | IC 95 % | P(top 2) | P(top 3) | puesto medio (IC) | manos medias | acaba por tope |", "|---|---|---|---|---|---|---|---|"]
    ind = {}
    for c in ids:
        regs = [datos[c][s] for s in validas]
        ind[c] = indicadores(regs)
        n = len(regs)
        g = int(sum(ind[c]["gana"]))
        lo, hi = wilson(g, n)
        m, h, _ = E.resumen_ic(ind[c]["puesto"])
        L.append(f"| {CONFIGS[c]['nombre']} | {100 * g / n:.1f} % | {100 * lo:.1f}-{100 * hi:.1f} | {100 * sum(ind[c]['top2']) / n:.1f} % | "
                 f"{100 * sum(ind[c]['top3']) / n:.1f} % | {m:.2f} (±{h:.2f}) | {statistics.fmean(r['manos'] for r in regs):.0f} | "
                 f"{100 * sum(r['tope'] for r in regs) / n:.0f} % |")
    comparaciones = [c for c in ids if c != "a"]
    gana_a = []
    if "a" in ids and comparaciones:
        L += ["", "Diferencias EMPAREJADAS contra (a), por semilla (IC 95 % por bootstrap; la última columna es el IC con corrección de Bonferroni "
                  f"para {len(comparaciones)} comparaciones, 98,75 %):", "",
              "| config | Δ P(ganar) | IC 95 % | IC 98,75 % | Δ P(top 2) | IC 95 % | Δ P(top 3) | IC 95 % | Δ puesto | IC 95 % |", "|---|---|---|---|---|---|---|---|---|---|"]
        pc = lambda t: f"{100 * t[0]:+.1f} pts"
        ci = lambda t: f"{100 * t[1]:+.1f} a {100 * t[2]:+.1f}"
        for c in comparaciones:
            g = bootstrap_dif(ind[c]["gana"], ind["a"]["gana"])
            gb = bootstrap_dif(ind[c]["gana"], ind["a"]["gana"], z=0.05 / len(comparaciones) / 2)
            t2, t3 = bootstrap_dif(ind[c]["top2"], ind["a"]["top2"]), bootstrap_dif(ind[c]["top3"], ind["a"]["top3"])
            pu = bootstrap_dif(ind[c]["puesto"], ind["a"]["puesto"])
            L.append(f"| {CONFIGS[c]['nombre']} | {pc(g)} | {ci(g)} | {ci(gb)} | {pc(t2)} | {ci(t2)} | {pc(t3)} | {ci(t3)} | {pu[0]:+.2f} | {pu[1]:+.2f} a {pu[2]:+.2f} |")
            if g[1] > 0:
                gana_a.append((c, g, gb))
        L.append("")
        if gana_a:
            for c, g, gb in gana_a:
                L.append(f"**{CONFIGS[c]['nombre']}: le gana a (a) en P(ganar) con el IC 95 % por encima de 0 ({pc(g)}, IC {ci(g)}); "
                         f"{'también con Bonferroni' if gb[1] > 0 else 'NO sobrevive a Bonferroni'}.** → proponer usarla solo en la final.")
        else:
            L.append("**Ninguna configuración le gana a (a) en P(ganar) con el IC 95 % por encima de 0: Bender juega la final igual que la clasificatoria.**")
    # quién gana las finales (sanidad de los rivales) y brazos del bandido
    L += ["", "Ganador de la mesa (config a, todas las semillas válidas):", ""]
    if "a" in ids:
        cuenta = {}
        for s in validas:
            cuenta[datos["a"][s]["ganador"]] = cuenta.get(datos["a"][s]["ganador"], 0) + 1
        L.append(", ".join(f"{t}: {100 * k / len(validas):.0f} %" for t, k in sorted(cuenta.items(), key=lambda x: -x[1])))
    if "e" in ids:
        uso = {}
        for s in validas:
            for b, k in (datos["e"][s].get("brazos") or {}).items():
                uso[b] = uso.get(b, 0) + k
        tot = sum(uso.values()) or 1
        L += ["", "Uso de brazos del bandido (e): " + ", ".join(f"{b} {100 * k / tot:.0f} %" for b, k in sorted(uso.items()))]
    tiempos = [datos[c][s]["dur_s"] for c in ids for s in validas]
    L += ["", f"Tiempo por final: media {statistics.fmean(tiempos):.0f} s (mediana {statistics.median(tiempos):.0f} s)."]
    texto = "\n".join(L)
    open(os.path.join(directorio, "informe.md"), "w", encoding="utf-8").write(texto)
    return texto


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nombre", default="fin1")
    ap.add_argument("--n", type=int, default=400, help="finales por configuración")
    ap.add_argument("--manos", type=int, default=400, help="tope de manos de la final (≈ 1 hora)")
    ap.add_argument("--configs", default="a,b,c,d,e")
    ap.add_argument("--paralelo", type=int, default=12)
    ap.add_argument("--max-mesa-s", type=int, default=3000)
    ap.add_argument("--solo-informe", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    directorio = os.path.join(E.SALIDAS, "final", args.nombre)
    os.makedirs(directorio, exist_ok=True)
    cids = [c for c in args.configs.split(",") if c]
    json.dump({"commit": os.environ.get("BENDER_COMMIT_COMPLETO"), "n": args.n, "manos": args.manos, "semilla": SEMILLA, "rivales": RIVALES,
               "configs": {c: CONFIGS[c] for c in cids}}, open(os.path.join(directorio, "configuraciones.json"), "w"), indent=1)
    semillas = [SEMILLA + i for i in range(args.n)]
    datos = {c: {} for c in cids}
    t0 = time.time()
    # Orden: semilla por semilla (a, b, c, d, e de la misma semilla juntas), así una corrida parada a la mitad sigue emparejada.
    trabajos = [(s, c) for s in semillas for c in cids]
    if args.solo_informe:
        for s, c in trabajos:
            ruta = os.path.join(directorio, c, f"t{s}", "resumen.json")
            if os.path.exists(ruta):
                datos[c][s] = json.load(open(ruta, encoding="utf-8"))
    else:
        print(f"[final] {len(trabajos)} finales ({args.n} × {len(cids)} configuraciones), {args.paralelo} en paralelo, tope {args.manos} manos", flush=True)
        with ThreadPoolExecutor(args.paralelo) as pool:
            futuros = [(s, c, pool.submit(correr_final, s, c, directorio, args.manos, args.max_mesa_s)) for s, c in trabajos]
            for i, (s, c, f) in enumerate(futuros):
                datos[c][s] = f.result()
                if (i + 1) % 10 == 0:
                    print(f"[final] {i + 1}/{len(trabajos)} listas ({(time.time() - t0) / 60:.0f} min)", flush=True)
    print(informe(directorio, datos, semillas, args))


if __name__ == "__main__":
    main()
