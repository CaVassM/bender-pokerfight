#!/usr/bin/env python3
"""Evaluación de Bender: bb/100 contra cada rival, con intervalo de confianza del 95 %.

Dos vías (decisión del equipo):
  1. HU  · arena heads-up con ida y vuelta (mismas cartas, asientos cambiados): da el
     bb/100 contra CADA rival con muy poca varianza. Un archivo de config por (rival, semilla).
  2. MESA · mesas de 5 con bin/mesa y tokens fijos (Bender + 4 rivales de entrenamiento),
     50 rondas, stack 10 000, ciegas 50/100, plazo 5 s: las condiciones del torneo. El orden
     de conexión se rota para rotar los asientos.

bb/100 = fichas ganadas en bb por cada 100 manos. Cada muestra es una pareja ida+vuelta (HU)
o una mesa (MESA); el IC es media ± t·sd/√n. Con las MISMAS semillas, dos versiones de
Bender se pueden comparar emparejadas (--comparar).

Rivales de entrenamiento: aleatorio, conservador, base, estadistico, bandido, espia.
Rivales de reserva: darwin y novato. Solo para la evaluación FINAL (--final): nunca para
elegir parámetros.

Uso (desde la raíz del kit):
  bender/.venv/Scripts/python.exe bender/pruebas/evaluar.py --etiqueta capa1-v1
  ... --etiqueta capa1-v2 --params bender/pruebas/variantes/x.json --comparar capa1-v1
"""

import argparse
import itertools
import json
import math
import os
import random
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIN = os.path.join(RAIZ, "bin")
EXE = ".exe" if os.name == "nt" else ""
BENDER_MAIN = os.path.join(RAIZ, "bender", "main.py")
# Las salidas van a BENDER_SALIDAS si existe (lo pone evaluar_fijo.py para que todas las evaluaciones, aunque corran
# desde worktrees de commits distintos, compartan carpeta y se puedan comparar con --comparar).
SALIDAS = os.environ.get("BENDER_SALIDAS") or os.path.join(RAIZ, "bender", "pruebas", "salidas")
ENTRENAMIENTO = ["aleatorio", "conservador", "base", "estadistico", "bandido", "espia"]
RESERVA = ["darwin", "novato"]
BB = 100
STACK_MESA = 10_000
T95 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26, 10: 2.23, 12: 2.18,
       15: 2.13, 20: 2.09, 25: 2.06, 30: 2.04}


def t95(df):
    for k in sorted(T95):
        if df <= k:
            return T95[k]
    return 1.96


def resumen_ic(xs):
    """media, mitad del IC 95 %, n."""
    n = len(xs)
    if n == 0:
        return float("nan"), float("nan"), 0
    m = statistics.fmean(xs)
    if n < 2:
        return m, float("nan"), n
    return m, t95(n - 1) * statistics.stdev(xs) / math.sqrt(n), n


def comando_rival(nombre, puerto, token):
    if nombre == "novato":                      # bot de Python: no tiene binario en bin/
        return [sys.executable, os.path.join(RAIZ, "bots", "novato", "bot.py"), "-addr", f"127.0.0.1:{puerto}",
                "-token", token, "-silencioso"]
    extra = {"estadistico": ["-simulaciones", "2000"], "bandido": ["-silencioso"], "espia": ["-silencioso"],
             "darwin": ["-silencioso"]}.get(nombre, [])
    return [os.path.join(BIN, nombre + EXE), "-addr", f"127.0.0.1:{puerto}", "-token", token] + extra


def comando_rival_arena(nombre):
    """Como en torneo-go.json: la arena agrega -addr y -token."""
    if nombre == "novato":
        return [sys.executable, os.path.join(RAIZ, "bots", "novato", "bot.py"), "-silencioso"]
    extra = {"estadistico": ["-simulaciones", "2000"], "bandido": ["-silencioso"], "espia": ["-silencioso"],
             "darwin": ["-silencioso"]}.get(nombre, [])
    return [os.path.join(BIN, nombre + EXE)] + extra


def archivo_params(dir_salida, params_usuario):
    """JSON de parámetros de Bender para las corridas: sin log de mensajes crudos (corridas largas)
    y, si se pidió, mezclado con las variantes del usuario."""
    base = {}
    if params_usuario:
        with open(params_usuario, encoding="utf-8") as f:
            base = json.load(f)
    base.setdefault("registro", {})["mensajes"] = False
    ruta = os.path.join(dir_salida, "params-bender.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(base, f)
    return ruta


def params_corrida(ruta_base, dir_run, memoria_dir=None):
    """Copia de los parámetros de la evaluación con la memoria de rivales (Capa 2) en la carpeta de ESTA
    corrida: ni las mesas en paralelo ni dos evaluaciones se pisan, y no hay "memoria heredada" entre
    corridas (cada mesa de evaluación empieza sin conocer a nadie, como la primera ronda del torneo).
    Con `memoria_dir` (campañas) la memoria se comparte entre mesas consecutivas a propósito."""
    with open(ruta_base, encoding="utf-8") as f:
        p = json.load(f)
    p.setdefault("rivales", {})["dir"] = memoria_dir or os.path.join(dir_run, "rivales")
    ruta = os.path.join(dir_run, "params-bender.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(p, f)
    return ruta


# --- Vía 1: arena heads-up ------------------------------------------------------------------------------

def correr_hu(rival, semilla, manos, dir_run, ruta_params, historial):
    os.makedirs(dir_run, exist_ok=True)
    ruta_params = params_corrida(ruta_params, dir_run)
    log = os.path.join(dir_run, "bender.jsonl")
    config = {
        "nombre": f"hu-{rival}-{semilla}", "formato": "round-robin", "puntuacion": "neto",
        "manos_por_enfrentamiento": manos, "ida_y_vuelta": True, "reponer_stack": True,
        "semilla": semilla, "paralelismo": 1, "penalizacion_timeout": 0, "guardar_historial": bool(historial),
        "salida": os.path.join(dir_run, "arena"),
        "mesa": {"ciega_chica": 50, "ciega_grande": 100, "stack": STACK_MESA, "timeout_ms": 5000, "espera_jugadores_ms": 20000},
        "participantes": [
            {"id": "bender", "nombre": "Bender", "comando": [sys.executable, BENDER_MAIN, "-silencioso", "-log", log, "-params", ruta_params]},
            {"id": rival, "nombre": rival, "comando": comando_rival_arena(rival)},
        ],
    }
    ruta = os.path.join(dir_run, "torneo.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(config, f)
    inicio = time.time()
    out = subprocess.run([os.path.join(BIN, "arena" + EXE), "correr", "-config", ruta], cwd=RAIZ, capture_output=True,
                         text=True, timeout=3600)
    duracion = time.time() - inicio
    with open(os.path.join(dir_run, "arena.out"), "w", encoding="utf-8") as f:
        f.write(out.stdout + "\n" + out.stderr)
    return leer_hu(os.path.join(dir_run, "arena", "enfrentamientos.jsonl"), duracion)


def leer_hu(ruta, duracion):
    """Una muestra por pareja ida+vuelta: bb/100 de Bender sobre las manos de las dos."""
    parejas, timeouts, manos_tot = {}, 0, 0
    if not os.path.exists(ruta):
        return {"muestras": [], "manos": 0, "timeouts": 0, "duracion": duracion}
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            r = json.loads(linea)
            b = next((p for p in r["puestos"] if p["id_participante"] == "bender"), None)
            if b is None or not b["manos_jugadas"]:
                continue
            clave = r["id"].replace("-vuelta", "")
            neto, manos = parejas.get(clave, (0, 0))
            parejas[clave] = (neto + b["neto"], manos + b["manos_jugadas"])
            timeouts += b["timeouts"]
            manos_tot += b["manos_jugadas"]
    muestras = [neto / BB / manos * 100.0 for neto, manos in parejas.values()]
    return {"muestras": muestras, "manos": manos_tot, "timeouts": timeouts, "duracion": duracion}


# --- Vía 2: mesas de 5 con bin/mesa --------------------------------------------------------------------------

def correr_mesa(indice, rivales, orden, rondas, puerto, dir_run, ruta_params, memoria_dir=None):
    """Una mesa: Bender + 4 rivales, conectados en el orden `orden` (rota los asientos)."""
    os.makedirs(dir_run, exist_ok=True)
    ruta_params = params_corrida(ruta_params, dir_run, memoria_dir)
    procesos, archivos = [], []

    def lanzar(comando, nombre, env=None):
        out = open(os.path.join(dir_run, nombre + ".out"), "w", encoding="utf-8")
        archivos.append(out)
        p = subprocess.Popen(comando, stdout=out, stderr=subprocess.STDOUT, cwd=RAIZ, env=env)
        procesos.append(p)
        return p

    inicio = time.time()
    mesa = lanzar([os.path.join(BIN, "mesa" + EXE), "-addr", f"127.0.0.1:{puerto}", "-jugadores", "6", "-min-jugadores", "5",
                   "-rondas", str(rondas), "-stack", str(STACK_MESA), "-ciega-chica", "50", "-ciega-grande", "100",
                   "-timeout-ms", "5000", "-id", f"mesa-{indice}"], "mesa")
    ruta_mesa = os.path.join(dir_run, "mesa.out")
    for _ in range(100):
        time.sleep(0.1)
        if "escuchando" in open(ruta_mesa, encoding="utf-8", errors="replace").read():
            break
    token_bender = f"bender-{indice}"
    env = dict(os.environ, BENDER_TOKEN=token_bender)
    log = os.path.join(dir_run, "bender.jsonl")
    try:
        for quien in orden:                               # el orden de conexión fija el asiento
            if quien == "bender":
                lanzar([sys.executable, BENDER_MAIN, "-addr", f"127.0.0.1:{puerto}", "-silencioso", "-log", log, "-params", ruta_params],
                       "bender", env)
            else:
                lanzar(comando_rival(quien, puerto, f"k-{quien}"), quien)
            time.sleep(0.4)
        try:
            mesa.wait(timeout=900)
        except subprocess.TimeoutExpired:
            pass
    finally:                                              # aunque algo falle, no dejar procesos huérfanos
        for p in procesos:
            if p.poll() is None:
                if os.name == "nt":                       # el python del venv lanza un hijo: matar el árbol
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
                else:
                    p.kill()
    duracion = time.time() - inicio
    for a in archivos:
        a.close()
    texto = open(ruta_mesa, encoding="utf-8", errors="replace").read()
    rondas_jugadas, fichas = 0, {}
    for linea in texto.splitlines():
        if "partida terminada" in linea:
            rondas_jugadas = int(linea.split(",")[1].split()[0])
        s = linea.strip()
        if s.startswith("#"):
            partes = s.split()
            fichas[partes[1]] = int(partes[2])
    if token_bender not in fichas or not rondas_jugadas:
        return {"muestra": None, "rondas": rondas_jugadas, "duracion": duracion, "rivales": rivales, "orden": orden}
    neto = fichas[token_bender] - STACK_MESA
    return {"muestra": neto / BB / rondas_jugadas * 100.0, "rondas": rondas_jugadas, "duracion": duracion,
            "rivales": rivales, "orden": orden, "final": fichas.get(token_bender)}


def combinaciones_de_mesas(n_mesas, rivales, semilla):
    """Cada mesa lleva 4 de los rivales; se recorren las C(n,4) combinaciones en orden barajado,
    y el orden de conexión de los 5 se baraja (rota los asientos)."""
    rng = random.Random(semilla)
    combos = list(itertools.combinations(rivales, 4))
    rng.shuffle(combos)
    out = []
    for i in range(n_mesas):
        c = list(combos[i % len(combos)])
        orden = c + ["bender"]
        rng.shuffle(orden)
        out.append((c, orden))
    return out


# --- Tiempos de decisión (de los registros de Bender) --------------------------------------------------------

def tiempos_de_decision(dir_raiz):
    ts, ns, paradas, por_calle = [], [], {}, {}
    for carpeta, _, archivos in os.walk(dir_raiz):
        for nombre in archivos:
            if nombre != "bender.jsonl":
                continue
            with open(os.path.join(carpeta, nombre), encoding="utf-8") as f:
                for linea in f:
                    if '"tipo":"decision"' not in linea[:80]:
                        continue
                    d = json.loads(linea)
                    ts.append(d["tiempo_s"])
                    ns.append(d.get("n_sim", 0))
                    por_calle.setdefault(d["etapa"], []).append(d["tiempo_s"])
                    info = d.get("info") or {}
                    for r in [info.get("equity") or {}] + list(info.get("equities_si_pagan") or []):
                        par = r.get("parada")
                        if par:
                            paradas[par] = paradas.get(par, 0) + 1
    if not ts:
        return None
    ts_s = sorted(ts)

    def pct(v, p):
        return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]
    con_sim = sorted(t for t, n in zip(ts, ns) if n > 0)
    return {"decisiones": len(ts), "mediana_ms": statistics.median(ts) * 1000, "p95_ms": pct(ts_s, 95) * 1000,
            "p99_ms": pct(ts_s, 99) * 1000, "max_ms": ts_s[-1] * 1000,
            "decisiones_con_simulacion": len(con_sim),
            "mediana_ms_con_sim": (statistics.median(con_sim) * 1000) if con_sim else None,
            "p95_ms_con_sim": (pct(con_sim, 95) * 1000) if con_sim else None,
            "n_sim_mediana": statistics.median([n for n in ns if n > 0]) if con_sim else None,
            "paradas": paradas,
            "por_calle": {k: {"n": len(v), "mediana_ms": statistics.median(v) * 1000, "p95_ms": pct(sorted(v), 95) * 1000}
                          for k, v in por_calle.items()}}


# --- Programa principal -------------------------------------------------------------------------------------------

def fila(nombre, xs):
    m, h, n = resumen_ic(xs)
    return f"| {nombre} | {m:+.1f} | ±{h:.1f} | {n} |" if n > 1 else f"| {nombre} | {m:+.1f} | n/d | {n} |"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--etiqueta", required=True, help="nombre de esta versión de Bender (guarda salidas/evaluaciones/<etiqueta>.json)")
    ap.add_argument("--params", default=None, help="JSON de parámetros de Bender (variante a evaluar)")
    ap.add_argument("--rivales", default=",".join(ENTRENAMIENTO))
    ap.add_argument("--final", action="store_true", help="permite los rivales de reserva (darwin, novato): SOLO evaluación final")
    ap.add_argument("--solo-hu", action="store_true")
    ap.add_argument("--solo-mesa", action="store_true")
    ap.add_argument("--semillas", type=int, default=3, help="semillas por rival en HU")
    ap.add_argument("--semilla-base", type=int, default=20261111)
    ap.add_argument("--manos", type=int, default=200, help="manos por enfrentamiento en HU (se juegan ida y vuelta)")
    ap.add_argument("--mesas", type=int, default=15, help="mesas de 5 jugadores")
    ap.add_argument("--rondas", type=int, default=50, help="manos por mesa de 5")
    ap.add_argument("--paralelo", type=int, default=4)
    ap.add_argument("--puerto-base", type=int, default=9300)
    ap.add_argument("--comparar", default=None, help="etiqueta de una evaluación anterior (mismas semillas)")
    ap.add_argument("--historial", action="store_true", help="guarda el historial de manos de la arena (cartas de todos)")
    args = ap.parse_args()

    rivales = [r for r in args.rivales.split(",") if r]
    reserva = [r for r in rivales if r in RESERVA]
    if reserva and not args.final:
        sys.exit(f"{reserva} son rivales de RESERVA: solo se usan en la evaluación final (--final), nunca para elegir parámetros.")
    desconocidos = [r for r in rivales if r not in ENTRENAMIENTO + RESERVA]
    if desconocidos:
        sys.exit(f"rivales desconocidos: {desconocidos}")

    dir_eval = os.path.join(SALIDAS, f"eval-{args.etiqueta}")
    os.makedirs(dir_eval, exist_ok=True)
    ruta_params = archivo_params(dir_eval, args.params)
    resultado = {"etiqueta": args.etiqueta, "commit": os.environ.get("BENDER_COMMIT"), "params": args.params,
                 "rivales": rivales, "semillas": args.semillas,
                 "semilla_base": args.semilla_base, "manos_hu": args.manos, "hu": {}, "mesa": {}}
    inicio = time.time()

    # --- HU ---
    if not args.solo_mesa:
        trabajos = [(r, args.semilla_base + s) for r in rivales for s in range(args.semillas)]
        print(f"[hu] {len(trabajos)} corridas de arena ({args.manos} manos ida y vuelta cada una), {args.paralelo} en paralelo...", flush=True)
        with ThreadPoolExecutor(args.paralelo) as pool:
            futuros = {t: pool.submit(correr_hu, t[0], t[1], args.manos, os.path.join(dir_eval, f"hu-{t[0]}-s{t[1]}"),
                                      ruta_params, args.historial) for t in trabajos}
            for (r, semilla), fut in futuros.items():
                d = fut.result()
                acc = resultado["hu"].setdefault(r, {"muestras": [], "claves": [], "manos": 0, "timeouts": 0, "duracion": 0.0})
                acc["muestras"] += d["muestras"]
                acc["claves"] += [f"{semilla}:{i}" for i in range(len(d["muestras"]))]
                acc["manos"] += d["manos"]
                acc["timeouts"] += d["timeouts"]
                acc["duracion"] += d["duracion"]

    # --- MESA ---
    if not args.solo_hu:
        plan = combinaciones_de_mesas(args.mesas, rivales, args.semilla_base)
        print(f"[mesa] {len(plan)} mesas de 5 ({args.rondas} manos), {args.paralelo} en paralelo...", flush=True)
        with ThreadPoolExecutor(args.paralelo) as pool:
            futuros = [pool.submit(correr_mesa, i, c, orden, args.rondas, args.puerto_base + i,
                                   os.path.join(dir_eval, f"mesa-{i}"), ruta_params) for i, (c, orden) in enumerate(plan)]
            mesas = [f.result() for f in futuros]
        validas = [m for m in mesas if m["muestra"] is not None]
        resultado["mesa"] = {"muestras": [m["muestra"] for m in validas], "claves": [str(i) for i, m in enumerate(mesas) if m["muestra"] is not None],
                             "rondas": sum(m["rondas"] for m in mesas), "duracion": sum(m["duracion"] for m in mesas),
                             "descartadas": len(mesas) - len(validas),
                             "por_rival": {r: [m["muestra"] for m in validas if r in m["rivales"]] for r in rivales}}
    resultado["tiempo_total_s"] = time.time() - inicio
    resultado["decisiones"] = tiempos_de_decision(dir_eval)

    ruta_json = os.path.join(SALIDAS, "evaluaciones", f"{args.etiqueta}.json")
    os.makedirs(os.path.dirname(ruta_json), exist_ok=True)
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=1)

    imprimir(resultado, args.comparar)
    print(f"\n(guardado en {ruta_json})")


def imprimir(res, comparar):
    ant = None
    if comparar:
        with open(os.path.join(SALIDAS, "evaluaciones", f"{comparar}.json"), encoding="utf-8") as f:
            ant = json.load(f)
    print(f"\n## Evaluación «{res['etiqueta']}»" + (f" (comparada con «{comparar}», mismas semillas)" if ant else ""))
    if res["hu"]:
        print("\n### Heads-up (arena, ida y vuelta): bb/100 de Bender, IC 95 %")
        print("| rival | bb/100 | IC 95 % | parejas | manos | timeouts |" + (" anterior | dif. emparejada |" if ant else ""))
        print("|---|---|---|---|---|---|" + ("---|---|" if ant else ""))
        todas = []
        for r, d in res["hu"].items():
            m, h, n = resumen_ic(d["muestras"])
            todas += d["muestras"]
            extra = ""
            if ant and r in ant["hu"]:
                a = ant["hu"][r]
                ma, _, _ = resumen_ic(a["muestras"])
                dic = dict(zip(a["claves"], a["muestras"]))
                difs = [x - dic[k] for k, x in zip(d["claves"], d["muestras"]) if k in dic]
                md, hd, nd = resumen_ic(difs)
                extra = f" {ma:+.1f} | {md:+.1f} ±{hd:.1f} |"
            print(f"| {r} | {m:+.1f} | ±{h:.1f} | {n} | {d['manos']} | {d['timeouts']} |{extra}")
        m, h, n = resumen_ic(todas)
        print(f"| **todos** | {m:+.1f} | ±{h:.1f} | {n} | {sum(d['manos'] for d in res['hu'].values())} | {sum(d['timeouts'] for d in res['hu'].values())} |")
        manos = sum(d["manos"] for d in res["hu"].values())
        dur = sum(d["duracion"] for d in res["hu"].values())
        print(f"\nManos por segundo de la arena heads-up: {manos / max(dur, 1e-9):.1f} manos/s por corrida (promedio; hay varias en paralelo)")
    if res.get("mesa") and res["mesa"].get("muestras"):
        mm = res["mesa"]
        print("\n### Mesas de 5 (bin/mesa): bb/100 de Bender, IC 95 %")
        print("| rivales en la mesa | bb/100 | IC 95 % | mesas |")
        print("|---|---|---|---|")
        print(fila("**todas**", mm["muestras"]))
        for r, xs in mm["por_rival"].items():
            if xs:
                print(fila(f"con {r}", xs))
        print(f"\nMesas descartadas por falta de resultado: {mm['descartadas']}. "
              f"Manos por segundo (mesa de 5): {mm['rondas'] / max(mm['duracion'], 1e-9):.2f} manos/s por mesa")
    d = res.get("decisiones")
    if d:
        print("\n### Tiempo por decisión de Bender")
        print(f"{d['decisiones']} decisiones: mediana {d['mediana_ms']:.1f} ms | p95 {d['p95_ms']:.1f} ms | p99 {d['p99_ms']:.1f} ms | máx {d['max_ms']:.0f} ms")
        if d["mediana_ms_con_sim"] is not None:
            print(f"Solo las que simularon ({d['decisiones_con_simulacion']}): mediana {d['mediana_ms_con_sim']:.1f} ms | p95 {d['p95_ms_con_sim']:.1f} ms | N mediana {d['n_sim_mediana']:.0f}")
        print(f"Paradas del Monte Carlo: {d['paradas']}")
        for calle, v in d["por_calle"].items():
            print(f"  {calle:8} n={v['n']:5} mediana {v['mediana_ms']:.1f} ms  p95 {v['p95_ms']:.1f} ms")


if __name__ == "__main__":
    main()
