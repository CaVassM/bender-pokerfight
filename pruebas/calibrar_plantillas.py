#!/usr/bin/env python3
"""Calibración de las plantillas postflop de §2.2 con el historial local (cartas de TODOS en TODAS las manos).

1. --generar: la arena juega una mesa única de 6 bots de ENTRENAMIENTO (aleatorio, conservador, base,
   estadistico, bandido, espia) con `guardar_historial` y `reponer_stack`: cada mano trae las cartas
   privadas de todos los que jugaron, no solo las de los showdowns.
2. Para cada acción postflop de cada bot se calcula la categoría de su mano en ese board (fuerte, media,
   proyecto, aire) y el contexto: ¿había una apuesta antes en la calle?
3. Se cuenta por grupo de tipo: TAG (base, estadistico, bandido, espia) y station (conservador):
     - enfrentando una apuesta:  retira / paga / sube   -> P(retira, paga, sube | categoría)
     - nadie apostó:             pasa / apuesta          -> P(apuesta | categoría)
4. Shrinkage hacia la plantilla actual con s = 20 pseudo-observaciones por celda (por fila de categoría y
   contexto): p = (conteo + s·p_actual) / (n + s). Así una categoría con pocas observaciones se queda
   cerca de la plantilla vigente y no se sobreajusta a los bots del kit.
Nit y maníaco no se tocan (no hay bots así en el kit). aleatorio y novato/darwin no entran.

Uso: bender/.venv/Scripts/python.exe bender/pruebas/calibrar_plantillas.py [--generar] [--semillas 8] [--manos 600]
Escribe bender/datos/calibracion_plantillas.json.
"""

import argparse
import glob
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RAIZ, "bender"))
import cartas as C          # noqa: E402
import poblacion as POB     # noqa: E402
import rangos as R          # noqa: E402
from params import PARAMS   # noqa: E402

BIN = os.path.join(RAIZ, "bin")
EXE = ".exe" if os.name == "nt" else ""
DIR = os.path.join(RAIZ, "bender", "pruebas", "salidas", "plantillas")
ENTRENAMIENTO = ["aleatorio", "conservador", "base", "estadistico", "bandido", "espia"]
GRUPOS = {"tag": ["base", "estadistico", "bandido", "espia"], "station": ["conservador"]}
CATS = [R.FUERTE, R.MEDIA, R.PROYECTO, R.AIRE]
S_SHRINK = 20.0
APUESTAS = ("bet", "raise", "allin")
CARTAS_DE_CALLE = {"flop": 3, "turn": 4, "river": 5}


def comando(bot):
    extra = {"estadistico": ["-simulaciones", "2000"], "bandido": ["-silencioso"], "espia": ["-silencioso"]}.get(bot, [])
    return [os.path.join(BIN, bot + EXE)] + extra


def generar(semilla, manos):
    d = os.path.join(DIR, f"s{semilla}")
    os.makedirs(d, exist_ok=True)
    cfg = {"nombre": f"plantillas-{semilla}", "formato": "mesa-unica", "puntuacion": "neto", "manos_por_enfrentamiento": manos,
           "reponer_stack": True, "semilla": semilla, "paralelismo": 1, "penalizacion_timeout": 0, "guardar_historial": True,
           "salida": os.path.join(d, "arena"),
           "mesa": {"ciega_chica": 50, "ciega_grande": 100, "stack": 10000, "timeout_ms": 5000, "espera_jugadores_ms": 20000},
           "participantes": [{"id": b, "nombre": b, "comando": comando(b)} for b in ENTRENAMIENTO]}
    ruta = os.path.join(d, "torneo.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    out = subprocess.run([os.path.join(BIN, "arena" + EXE), "correr", "-config", ruta], cwd=RAIZ, capture_output=True, text=True, timeout=3000)
    return out.returncode


def contar():
    """{grupo: {"faced": {cat: [ret, paga, sube]}, "libre": {cat: [pasa, apuesta]}}} y el nº de manos."""
    def vacio():
        return {"faced": {c: [0, 0, 0] for c in CATS}, "libre": {c: [0, 0] for c in CATS}}
    cuentas = {g: vacio() for g in GRUPOS}
    cuentas_bot = {b: vacio() for b in ENTRENAMIENTO}
    bot_a_grupo = {b: g for g, bs in GRUPOS.items() for b in bs}
    cache = POB.CacheCategorias()
    manos = 0
    for ruta in glob.glob(os.path.join(DIR, "s*", "arena", "manos", "*.jsonl")):
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                m = json.loads(linea)
                manos += 1
                tab = [C.carta(c["rango"], c["palo"]) for c in (m.get("comunitarias") or [])]
                priv = {i: tuple(sorted(C.carta(c["rango"], c["palo"]) for c in cs)) for i, cs in (m.get("privadas") or {}).items()}
                hubo, fuera = {}, set()
                for a in m["acciones"]:
                    i, et, t = a["id_jugador"], a["etapa"], a["accion"]["tipo"]
                    if i in fuera:
                        continue
                    n = CARTAS_DE_CALLE.get(et)
                    if et != "preflop" and n and len(tab) >= n and i in priv and i in cuentas_bot:
                        board = tuple(sorted(tab[:n]))
                        if not (set(priv[i]) & set(board)):
                            cat = cache.de(priv[i], board)
                            destinos = [cuentas_bot[i]] + ([cuentas[bot_a_grupo[i]]] if i in bot_a_grupo else [])
                            for g in destinos:
                                if hubo.get(et):
                                    if t == "fold":
                                        g["faced"][cat][0] += 1
                                    elif t == "call":
                                        g["faced"][cat][1] += 1
                                    elif t in APUESTAS:
                                        g["faced"][cat][2] += 1
                                else:
                                    if t == "check":
                                        g["libre"][cat][0] += 1
                                    elif t in APUESTAS:
                                        g["libre"][cat][1] += 1
                    if t in APUESTAS:
                        hubo[et] = True
                    if t == "fold":
                        fuera.add(i)
    return cuentas, manos, cuentas_bot


def actuales(grupo):
    """Plantilla del .tex (prior del shrinkage), siempre la PROVISIONAL, para que la calibración sea reproducible
    aunque params.py ya traiga los valores calibrados."""
    from params import PLANTILLAS_TEX, PROB_APUESTA_TEX
    pl = PLANTILLAS_TEX["promedio" if grupo == "tag" else grupo]
    mult = PARAMS["prob_apuesta"]["mult"].get(grupo, 1.0)
    libre = {c: min(PARAMS["prob_apuesta"]["tope"], PROB_APUESTA_TEX[c] * mult) for c in CATS}
    return pl, libre


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--generar", action="store_true")
    ap.add_argument("--semillas", type=int, default=8)
    ap.add_argument("--manos", type=int, default=600)
    args = ap.parse_args()
    if args.generar:
        with ThreadPoolExecutor(4) as pool:
            rc = list(pool.map(lambda s: generar(20270000 + s, args.manos), range(args.semillas)))
        print("códigos de salida de la arena:", rc, flush=True)
    cuentas, manos, cuentas_bot = contar()
    print(f"\n{manos} manos leídas del historial.\n")
    resultado = {"manos": manos, "s": S_SHRINK, "grupos": {}}
    for g in GRUPOS:
        pl, libre = actuales(g)
        print(f"### {g.upper()}  (bots: {', '.join(GRUPOS[g])})")
        print("| categoría | n enfrentando | retira / paga / sube medido | actual (.tex) | NUEVO | n libre | apuesta medido | actual | NUEVO |")
        print("|---|---|---|---|---|---|---|---|---|")
        nueva_pl, nueva_libre = {}, {}
        for c in CATS:
            cf, cl = cuentas[g]["faced"][c], cuentas[g]["libre"][c]
            nf, nl = sum(cf), sum(cl)
            fila = [(cf[k] + S_SHRINK * pl[c][k]) / (nf + S_SHRINK) for k in range(3)]
            lib = (cl[1] + S_SHRINK * libre[c]) / (nl + S_SHRINK)
            nueva_pl[c], nueva_libre[c] = [round(x, 3) for x in fila], round(lib, 3)
            medido = " / ".join(f"{x / nf:.2f}" for x in cf) if nf else "—"
            act = " / ".join(f"{x:.2f}" for x in pl[c])
            nuevo = " / ".join(f"{x:.2f}" for x in nueva_pl[c])
            print(f"| {c} | {nf} | {medido} | {act} | **{nuevo}** | {nl} | {(cl[1] / nl if nl else float('nan')):.2f} | {libre[c]:.2f} | **{nueva_libre[c]:.2f}** |")
        resultado["grupos"][g] = {"cuentas": cuentas[g], "plantilla": nueva_pl, "prob_apuesta": nueva_libre,
                                  "plantilla_anterior": pl, "prob_apuesta_anterior": libre}
        print()
    # --- Por bot (contraestrategia §3.4): shrinkage s=20 hacia la plantilla CALIBRADA de su grupo ---
    print("### POR BOT (shrinkage s=20 hacia la plantilla calibrada de su grupo; aleatorio, hacia 1/3 y 0,5)")
    print("| bot | categoría | n enfrentando | retira / paga / sube | n libre | apuesta |")
    print("|---|---|---|---|---|---|")
    resultado["bots"] = {}
    for b in ENTRENAMIENTO:
        g = next((g for g, bs in GRUPOS.items() if b in bs), None)
        if g:
            pl0, lib0 = resultado["grupos"][g]["plantilla"], resultado["grupos"][g]["prob_apuesta"]
        else:
            pl0, lib0 = {c: [1 / 3] * 3 for c in CATS}, {c: 0.5 for c in CATS}
        pl_b, lib_b = {}, {}
        for c in CATS:
            cf, cl = cuentas_bot[b]["faced"][c], cuentas_bot[b]["libre"][c]
            nf, nl = sum(cf), sum(cl)
            pl_b[c] = [round((cf[k] + S_SHRINK * pl0[c][k]) / (nf + S_SHRINK), 3) for k in range(3)]
            lib_b[c] = round((cl[1] + S_SHRINK * lib0[c]) / (nl + S_SHRINK), 3)
            print(f"| {b} | {c} | {nf} | " + " / ".join(f"{x:.2f}" for x in pl_b[c]) + f" | {nl} | {lib_b[c]:.2f} |")
        resultado["bots"][b] = {"plantilla": pl_b, "prob_apuesta": lib_b, "cuentas": cuentas_bot[b]}
    ruta = os.path.join(RAIZ, "bender", "datos", "calibracion_plantillas.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=1)
    print(f"(guardado en {ruta})")


if __name__ == "__main__":
    main()
