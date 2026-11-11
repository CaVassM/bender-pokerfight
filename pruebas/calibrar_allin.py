#!/usr/bin/env python3
"""Calibración de los ALL-IN (§1.9 R_paga y §2.8 rango de quien empuja) con el historial local con las cartas de TODOS.

Fuente: la arena juega una mesa única de 6 bots de ENTRENAMIENTO (aleatorio, conservador, base, estadistico, bandido,
espia) con `guardar_historial` y `reponer_stack` (todas las manos arrancan a 100 bb): cada mano trae las cartas
privadas de todos. Es el mismo historial que usa calibrar_plantillas.py (aquí se genera más en otra carpeta).

Se mide, por bot y por grupo de tipo (TAG = base, estadistico, bandido, espia; station = conservador; aleatorio):

  PAGA (§1.9 R_paga / fold equity f)
     P(paga | enfrenta un all-in)  por calle (preflop / postflop):  n y pagos.
     + comprobación de que paga con sus MANOS MÁS FUERTES (el modelo asume que quien paga es la fracción c(x) más
       fuerte del rango): AUC = P(la mano que paga es más fuerte que la que se retira).
  EMPUJA (§2.8)
     preflop: qué manos empuja all-in: el top-% de manos (ranking de 169 clases) que contiene el 90 % / 75 % / 50 % de sus
              all-in, y n.
     postflop: P(all-in | categoría de la mano, ¿había apuesta antes en la calle?) por categoría: n y all-in.

Shrinkage hacia lo ACTUAL con s = 20 pseudo-observaciones (se aplica al usar, en poblacion.py/capa1.py: p = (k + s·p_actual)/(n + s)).
Solo cuenta lo observado con stacks de 100 bb: el modelo lo usa únicamente en modo profundo (stack efectivo > 25 bb).
Nit y maníaco no se tocan (no hay bots así en el kit). darwin y novato (reserva) NO entran.

Uso: bender/.venv/Scripts/python.exe bender/pruebas/calibrar_allin.py [--generar] [--semillas 40] [--manos 600]
Escribe bender/datos/calibracion_allin.json y un bloque listo para pegar en params.py.
"""

import argparse
import glob
import json
import math
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RAIZ, "bender"))
import cartas as C          # noqa: E402
import poblacion as POB     # noqa: E402
import rangos as R          # noqa: E402

BIN = os.path.join(RAIZ, "bin")
EXE = ".exe" if os.name == "nt" else ""
DIR = os.path.join(RAIZ, "bender", "pruebas", "salidas", "allin")
ENTRENAMIENTO = ["aleatorio", "conservador", "base", "estadistico", "bandido", "espia"]
# Sin grupo "station": conservador (que nunca paga ni empuja un all-in) NO representa a una station genérica (decisión del
# usuario en el paso 5: las plantillas genéricas no se calibran con un bot concreto). Conservador queda como bot propio.
GRUPOS = {"tag": ["base", "estadistico", "bandido", "espia"], "aleatorio": ["aleatorio"]}
BOT_A_GRUPO = {b: g for g, bs in GRUPOS.items() for b in bs}
CATS = [R.FUERTE, R.MEDIA, R.PROYECTO, R.AIRE]
APUESTAS = ("bet", "raise", "allin")
CARTAS_DE_CALLE = {"flop": 3, "turn": 4, "river": 5}
SEMILLA0 = 20280000


def comando(bot):
    extra = {"estadistico": ["-simulaciones", "2000"], "bandido": ["-silencioso"], "espia": ["-silencioso"]}.get(bot, [])
    return [os.path.join(BIN, bot + EXE)] + extra


def generar(semilla, manos):
    d = os.path.join(DIR, f"s{semilla}")
    if glob.glob(os.path.join(d, "arena", "manos", "*.jsonl")):
        return 0                                          # reanudable
    os.makedirs(d, exist_ok=True)
    cfg = {"nombre": f"allin-{semilla}", "formato": "mesa-unica", "puntuacion": "neto", "manos_por_enfrentamiento": manos,
           "reponer_stack": True, "semilla": semilla, "paralelismo": 1, "penalizacion_timeout": 0, "guardar_historial": True,
           "salida": os.path.join(d, "arena"),
           "mesa": {"ciega_chica": 50, "ciega_grande": 100, "stack": 10000, "timeout_ms": 5000, "espera_jugadores_ms": 20000},
           "participantes": [{"id": b, "nombre": b, "comando": comando(b)} for b in ENTRENAMIENTO]}
    ruta = os.path.join(d, "torneo.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    out = subprocess.run([os.path.join(BIN, "arena" + EXE), "correr", "-config", ruta], cwd=RAIZ, capture_output=True, text=True, timeout=3600)
    return out.returncode


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def cuantil(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(math.ceil(q * len(v))) - 1)] if v else float("nan")


def contar(carpetas):
    """Recorre el historial y devuelve los conteos por bot."""
    def vacio():
        return {"paga": {"pre": [0, 0], "post": [0, 0]},          # [n que enfrentan all-in, pagan]
                "paga_pct": {"pre": {"paga": [], "retira": []}},   # top-% de la mano (menor = más fuerte) para el AUC
                "empuja_pre": [],                                  # top-% de cada all-in preflop
                "empuja_post": {"faced": {c: [0, 0] for c in CATS}, "libre": {c: [0, 0] for c in CATS}}}   # [oportunidades, all-in]
    cuentas = {b: vacio() for b in ENTRENAMIENTO}
    cache = POB.CacheCategorias()
    pct_clase = {}
    manos = 0
    for carpeta in carpetas:
        for ruta in glob.glob(os.path.join(carpeta, "arena", "manos", "*.jsonl")):
            with open(ruta, encoding="utf-8") as f:
                for linea in f:
                    m = json.loads(linea)
                    manos += 1
                    tab = [C.carta(c["rango"], c["palo"]) for c in (m.get("comunitarias") or [])]
                    priv = {i: tuple(sorted(C.carta(c["rango"], c["palo"]) for c in cs)) for i, cs in (m.get("privadas") or {}).items()}
                    hubo, allin_previo, fuera = {}, {}, set()
                    for a in m["acciones"]:
                        i, et, t = a["id_jugador"], a["etapa"], a["accion"]["tipo"]
                        if i in fuera:
                            continue
                        if i in cuentas and i in priv:
                            combo = priv[i]
                            c = cuentas[i]
                            g = "pre" if et == "preflop" else "post"
                            if et == "preflop":
                                clase = R.clase_de_combo(*combo)
                                if clase not in pct_clase:
                                    pct_clase[clase] = R.pct_acumulado(clase)
                                pct = pct_clase[clase]
                                if allin_previo.get(et):                                  # enfrenta un all-in
                                    if t in ("call", "fold"):
                                        c["paga"]["pre"][0] += 1
                                        c["paga"]["pre"][1] += t == "call"
                                        c["paga_pct"]["pre"]["paga" if t == "call" else "retira"].append(pct)
                                elif t == "allin":
                                    c["empuja_pre"].append(pct)
                            else:
                                n = CARTAS_DE_CALLE.get(et)
                                if n and len(tab) >= n and not (set(combo) & set(tab[:n])):
                                    board = tuple(sorted(tab[:n]))
                                    cat = cache.de(combo, board)
                                    if allin_previo.get(et):
                                        if t in ("call", "fold"):
                                            c["paga"]["post"][0] += 1
                                            c["paga"]["post"][1] += t == "call"
                                    else:
                                        ctx = "faced" if hubo.get(et) else "libre"
                                        c["empuja_post"][ctx][cat][0] += 1
                                        c["empuja_post"][ctx][cat][1] += t == "allin"
                        if t in APUESTAS:
                            hubo[et] = True
                        if t == "allin":
                            allin_previo[et] = True
                        if t == "fold":
                            fuera.add(i)
    return cuentas, manos


def sumar(cs):
    """Suma los conteos de varios bots (para un grupo)."""
    tot = None
    for c in cs:
        if tot is None:
            tot = json.loads(json.dumps(c))
            continue
        for g in ("pre", "post"):
            for k in (0, 1):
                tot["paga"][g][k] += c["paga"][g][k]
        tot["paga_pct"]["pre"]["paga"] += c["paga_pct"]["pre"]["paga"]
        tot["paga_pct"]["pre"]["retira"] += c["paga_pct"]["pre"]["retira"]
        tot["empuja_pre"] += c["empuja_pre"]
        for ctx in ("faced", "libre"):
            for cat in CATS:
                for k in (0, 1):
                    tot["empuja_post"][ctx][cat][k] += c["empuja_post"][ctx][cat][k]
    return tot


def auc(paga, retira):
    """P(la mano que paga es más fuerte que la que se retira) (top-% menor = más fuerte); empates cuentan 1/2."""
    if not paga or not retira:
        return float("nan")
    r = sorted(retira)
    import bisect
    s = 0.0
    for p in paga:
        lo, hi = bisect.bisect_left(r, p), bisect.bisect_right(r, p)
        s += (len(r) - hi) + 0.5 * (hi - lo)          # retiros con top-% mayor (más débiles) + empates/2
    return s / (len(paga) * len(r))


def serializar(c):
    """Lo que va a params.py: solo conteos y cuantiles (el AUC y las listas son para el informe)."""
    pre = c["empuja_pre"]
    return {"paga": c["paga"],
            "empuja_pre": {"n": len(pre), "q90": round(cuantil(pre, 0.90), 1) if pre else None,
                           "q75": round(cuantil(pre, 0.75), 1) if pre else None, "q50": round(cuantil(pre, 0.50), 1) if pre else None},
            "empuja_post": c["empuja_post"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--generar", action="store_true")
    ap.add_argument("--semillas", type=int, default=40)
    ap.add_argument("--manos", type=int, default=600)
    ap.add_argument("--paralelo", type=int, default=4)
    ap.add_argument("--incluir-plantillas", action="store_true", help="suma también las 4 800 manos de calibrar_plantillas.py")
    args = ap.parse_args()
    if args.generar:
        with ThreadPoolExecutor(args.paralelo) as pool:
            rc = list(pool.map(lambda s: generar(SEMILLA0 + s, args.manos), range(args.semillas)))
        print("códigos de salida de la arena:", rc, flush=True)
    carpetas = sorted(glob.glob(os.path.join(DIR, "s*")))
    if args.incluir_plantillas:
        carpetas += sorted(glob.glob(os.path.join(RAIZ, "bender", "pruebas", "salidas", "plantillas", "s*")))
    cuentas, manos = contar(carpetas)
    grupos = {g: sumar([cuentas[b] for b in bs]) for g, bs in GRUPOS.items()}
    print(f"\n{manos} manos leídas del historial ({len(carpetas)} carpetas).\n")

    todo = {**{b: cuentas[b] for b in ENTRENAMIENTO}, **{f"[{g}]": grupos[g] for g in GRUPOS}}
    print("### PAGA un all-in (a 100 bb)")
    print("| bot / grupo | preflop: enfrentan | pagan | % (IC 95 %) | AUC (¿paga con lo más fuerte?) | postflop: enfrentan | pagan | % (IC 95 %) |")
    print("|---|---|---|---|---|---|---|---|")
    for nombre, c in todo.items():
        n1, k1 = c["paga"]["pre"]
        n2, k2 = c["paga"]["post"]
        l1, h1 = wilson(k1, n1)
        l2, h2 = wilson(k2, n2)
        a = auc(c["paga_pct"]["pre"]["paga"], c["paga_pct"]["pre"]["retira"])
        pp = lambda k, n: f"{100 * k / n:.1f}" if n else "—"
        print(f"| {nombre} | {n1} | {k1} | {pp(k1, n1)} ({100 * l1:.0f}-{100 * h1:.0f}) | {a:.3f} | {n2} | {k2} | {pp(k2, n2)} ({100 * l2:.0f}-{100 * h2:.0f}) |")
    print("\n### EMPUJA all-in preflop: top-% de manos que contiene el 50 / 75 / 90 % de sus all-in")
    print("| bot / grupo | all-in preflop | mediana | q75 | q90 |\n|---|---|---|---|---|")
    for nombre, c in todo.items():
        pre = c["empuja_pre"]
        if pre:
            print(f"| {nombre} | {len(pre)} | top {cuantil(pre, .5):.1f} % | top {cuantil(pre, .75):.1f} % | top {cuantil(pre, .9):.1f} % |")
        else:
            print(f"| {nombre} | 0 | — | — | — |")
    print("\n### EMPUJA all-in postflop: P(all-in | categoría, contexto)")
    print("| bot / grupo | contexto | " + " | ".join(CATS) + " |\n|---|---|" + "---|" * len(CATS))
    for nombre, c in todo.items():
        for ctx in ("faced", "libre"):
            fila = []
            for cat in CATS:
                n, k = c["empuja_post"][ctx][cat]
                fila.append(f"{100 * k / n:.1f} % ({k}/{n})" if n else "—")
            print(f"| {nombre} | {ctx} | " + " | ".join(fila) + " |")

    resultado = {"manos": manos, "carpetas": len(carpetas),
                 "bots": {b: serializar(cuentas[b]) for b in ENTRENAMIENTO},
                 "grupos": {g: serializar(grupos[g]) for g in GRUPOS},
                 "auc_paga_preflop": {nombre: auc(c["paga_pct"]["pre"]["paga"], c["paga_pct"]["pre"]["retira"]) for nombre, c in todo.items()}}
    ruta = os.path.join(RAIZ, "bender", "datos", "calibracion_allin.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=1)
    # El módulo que lee params.py (conteos y cuantiles; el shrinkage se aplica al usarlos).
    import pprint
    datos = {"bots": resultado["bots"], "grupos": resultado["grupos"]}
    modulo = os.path.join(RAIZ, "bender", "calibracion_allin.py")
    with open(modulo, "w", encoding="utf-8") as f:
        f.write('"""Datos de pruebas/calibrar_allin.py (NO editar a mano; se regenera con esa herramienta).\n\n'
                f'Medidos con {manos} manos del historial local con las cartas de todos (6 bots de entrenamiento, 100 bb).\n'
                'paga: [enfrentan un all-in, pagan] por calle; empuja_pre: n de all-in preflop y top-% que contiene el 50/75/90 %;\n'
                'empuja_post: [oportunidades, all-in] por categoría de la mano y contexto.\n"""\n\n'
                "CALIBRACION_ALLIN = " + pprint.pformat(datos, width=150, sort_dicts=False) + "\n")
    print(f"\n(guardado en {ruta} y {modulo})")


if __name__ == "__main__":
    main()
