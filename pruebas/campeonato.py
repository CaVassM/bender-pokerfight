#!/usr/bin/env python3
"""Métrica del campeonato: P(sobrevivir 10 rondas) y P(top 6) de Bender en el formato REAL de la clasificatoria.

El kit no trae ese formato; `bender/herramientas/campeonato` (Go, compilado a bin/campeonato.exe) lo simula con el
motor real del kit: 10 rondas, mesas de 5 (algunas de 6) sorteadas de nuevo cada ronda, 50 manos por mesa, ciegas fijas
50/100, las fichas se arrastran de una ronda a la siguiente, eliminación al llegar a 0 y clasifican los 6 con más fichas.

Este script arma el campo (varias copias de cada bot del kit + Bender, con alias aleatorios estables), lanza MUCHOS
campeonatos con semillas fijas (las mismas semillas = mismo sorteo de mesas y mismas cartas en la primera ronda, así se
comparan versiones de Bender de forma emparejada) y agrega:
  - P(sobrevivir las 10 rondas), P(top 6), puesto medio, P(terminar con más de 10 000);
  - tasa de quiebra por mesa de Bender y de cada tipo de bot del kit (todas las rondas y solo la ronda 1, donde todos
    parten con 10 000);
  - bb/100 de Bender (fichas netas por mano jugada, agrupadas por campeonato);
  - con --comparar: diferencias emparejadas contra otra etiqueta.

Uso (desde la raíz del kit; compilar antes: go build -o bin/campeonato.exe ./bender/herramientas/campeonato):
  bender/.venv/Scripts/python.exe bender/pruebas/campeonato.py --etiqueta camp-v1 --torneos 100 --paralelo 6
  ... --etiqueta camp-u10k --params variantes/u10k.json --comparar camp-v1
"""

import argparse
import json
import math
import os
import random
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evaluar as E  # noqa: E402

RAIZ, BIN, EXE, SALIDAS = E.RAIZ, E.BIN, E.EXE, E.SALIDAS
STACK = 10_000
BB = 100
# Rival "bender_v1": copias de Bender como equipos fuertes DESCONOCIDOS (no son bots del kit). Por defecto es el código que se
# evalúa con la utilidad apagada (riesgo neutral); con --bender-v1-dir corre el main.py de otra carpeta (p. ej. el worktree del tag
# v1-probabilistico). Cada copia lleva su propia carpeta de memoria y su propio log.
BENDER_V1_DIR = None
# Fijado a «v1.2-fix con la utilidad apagada»: las reglas nuevas (limpers) también apagadas aunque cambien los valores por defecto.
PARAMS_BENDER_V1 = {"riesgo": {"utilidad": False}, "apertura": {"limpers_menu": False}}
# Copias de Bender con OTRO estilo (campo «desconocido» del paso 2 de la Capa 3): corren el código que se evalúa con estos cambios.
# Los rangos de apertura son los de params.py × la escala (tope 100 %); deben coincidir con apertura.top_pos de params.py.
TOP_POS_BASE = {"UTG": 14.3, "HJ": 18.9, "CO": 25.5, "BTN": 43.3, "SB": 33.0, "BTN_SB_HU": 70.0}


def _top_pos(escala):
    return {k: round(min(100.0, v * escala), 2) for k, v in TOP_POS_BASE.items()}


COPIAS_BENDER = {
    # K = 40 000 (casi neutral al riesgo), sin las reglas de solo valor y con rangos de apertura 15 % más anchos
    "bender_agresivo": {"riesgo": {"K": 40_000},
                        "decision": {"allin_profundo_solo_valor": False, "solo_valor_sobre_apuesta": False},
                        "apertura": {"top_pos": _top_pos(1.15)}},
    # K = 4 000 (más averso al riesgo) y rangos de apertura 15 % más estrechos
    "bender_prudente": {"riesgo": {"K": 4_000}, "apertura": {"top_pos": _top_pos(0.85)}},
}


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def campo_de(texto):
    out = []
    for par in texto.split(","):
        nombre, _, n = par.partition(":")
        out.append((nombre.strip(), int(n or 1)))
    return out


def armar(semilla, campo, ruta_params_bender, dir_t):
    """Participantes (con alias aleatorios estables, en orden fijado por la semilla) y el comando de cada uno."""
    rng = random.Random(semilla)
    tipos = [n for n, k in campo for _ in range(k)] + ["bender"]
    rng.shuffle(tipos)
    usados, partes = set(), []
    for tipo in tipos:
        while True:
            alias = "j-" + "".join(rng.choice("0123456789abcdef") for _ in range(6))
            if alias not in usados:
                usados.add(alias)
                break
        if tipo == "bender":
            cmd = [sys.executable, E.BENDER_MAIN, "-silencioso", "-params", ruta_params_bender, "-log", os.path.join(dir_t, "bender.jsonl")]
        elif tipo == "bender_v1" or tipo in COPIAS_BENDER:
            ruta_rival = os.path.join(dir_t, f"params-{alias}.json")
            propios = PARAMS_BENDER_V1 if tipo == "bender_v1" else COPIAS_BENDER[tipo]
            with open(ruta_rival, "w", encoding="utf-8") as f:
                json.dump({**propios, "rivales": {"dir": os.path.join(dir_t, f"rivales-{alias}")}, "registro": {"mensajes": False}}, f)
            main_v1 = os.path.join(BENDER_V1_DIR, "main.py") if (BENDER_V1_DIR and tipo == "bender_v1") else E.BENDER_MAIN
            cmd = [sys.executable, main_v1, "-silencioso", "-params", ruta_rival, "-log", os.path.join(dir_t, f"{alias}.jsonl")]
        else:
            cmd = E.comando_rival_arena(tipo)
        partes.append({"id": alias, "tipo": tipo, "comando": cmd, "directorio": RAIZ})
    return partes


def correr_torneo(semilla, campo, ruta_params, dir_base, rondas, manos):
    dir_t = os.path.join(dir_base, f"t{semilla}")
    os.makedirs(dir_t, exist_ok=True)
    ruta_res = os.path.join(dir_t, "resultado.json")
    if os.path.exists(ruta_res):                         # reanudable: no se repite un campeonato ya jugado
        return json.load(open(ruta_res, encoding="utf-8")), 0.0
    with open(ruta_params, encoding="utf-8") as f:
        p = json.load(f)
    p.setdefault("rivales", {})["dir"] = os.path.join(dir_t, "rivales")        # la memoria se acumula entre rondas
    p.setdefault("registro", {})["mensajes"] = False
    ruta_p = os.path.join(dir_t, "params-bender.json")
    with open(ruta_p, "w", encoding="utf-8") as f:
        json.dump(p, f)
    cfg = {"semilla": semilla, "rondas": rondas, "manos": manos, "ciega_chica": 50, "ciega_grande": 100, "stack": STACK,
           "timeout_ms": 5000, "participantes": armar(semilla, campo, ruta_p, dir_t)}
    ruta_cfg = os.path.join(dir_t, "torneo.json")
    with open(ruta_cfg, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    t0 = time.time()
    r = subprocess.run([os.path.join(BIN, "campeonato" + EXE), "-config", ruta_cfg, "-salida", ruta_res], cwd=RAIZ,
                       capture_output=True, text=True, timeout=3600)
    if r.returncode != 0 or not os.path.exists(ruta_res):
        raise RuntimeError(f"campeonato {semilla} falló: {r.stderr[-500:]}")
    return json.load(open(ruta_res, encoding="utf-8")), time.time() - t0


def resumir_torneo(res):
    """Registro por campeonato: lo de Bender y todas las jugadas de mesa (para las tasas de quiebra por tipo)."""
    bender =next(f for f in res["final"] if f["tipo"] == "bender")
    jugadas = []
    for ronda in res["rondas"]:
        for mesa in ronda:
            if mesa.get("error"):
                jugadas.append({"error": mesa["error"], "ronda": mesa["ronda"]})
                continue
            for j in mesa["jugadores"]:
                jugadas.append({"tipo": j["tipo"], "ronda": mesa["ronda"], "antes": j["antes"], "despues": j["despues"],
                                "manos": j["manos"], "timeouts": j["timeouts"], "n_mesa": len(mesa["jugadores"])})
    por_tipo = {}
    for f in res["final"]:
        d = por_tipo.setdefault(f["tipo"], {"n": 0, "sobrevive": 0, "top6": 0, "puesto": []})
        d["n"] += 1
        d["sobrevive"] += f["eliminado_en"] == 0
        d["top6"] += f["puesto"] <= 6
        d["puesto"].append(f["puesto"])
    return {"semilla": res["semilla"], "n_participantes": len(res["final"]),
            "bender": {"puesto": bender["puesto"], "fichas": bender["fichas"], "eliminado_en": bender["eliminado_en"]},
            "jugadas": jugadas, "por_tipo": por_tipo}


def bootstrap_dif(xs, ys, B=2000, rng=None):
    """IC 95 % de mean(xs) − mean(ys) emparejado (cada par = un campeonato con la misma semilla)."""
    rng = rng or random.Random(1)
    d = [a - b for a, b in zip(xs, ys)]
    n = len(d)
    ms = sorted(statistics.fmean(rng.choices(d, k=n)) for _ in range(B))
    return statistics.fmean(d), ms[int(0.025 * B)], ms[int(0.975 * B)]


def agregar(registros):
    n = len(registros)
    surv = [1.0 if r["bender"]["eliminado_en"] == 0 else 0.0 for r in registros]
    top6 = [1.0 if r["bender"]["puesto"] <= 6 else 0.0 for r in registros]
    arriba = [1.0 if (r["bender"]["eliminado_en"] == 0 and r["bender"]["fichas"] > STACK) else 0.0 for r in registros]
    puesto = [r["bender"]["puesto"] for r in registros]
    out = {"torneos": n, "participantes": registros[0]["n_participantes"] if registros else 0,
           "p_sobrevivir": (sum(surv) / n, *wilson(int(sum(surv)), n)),
           "p_top6": (sum(top6) / n, *wilson(int(sum(top6)), n)),
           "p_arriba_10000": (sum(arriba) / n, *wilson(int(sum(arriba)), n)),
           "puesto_medio": statistics.fmean(puesto), "fichas_medias": statistics.fmean(r["bender"]["fichas"] for r in registros)}
    # tasa de quiebra por mesa y bb/100 (todas las rondas y ronda 1)
    q = {}
    for r in registros:
        for j in r["jugadas"]:
            if "tipo" not in j:
                continue
            for clave in ("todas", "ronda1"):
                if clave == "ronda1" and j["ronda"] != 1:
                    continue
                d = q.setdefault(j["tipo"], {}).setdefault(clave, {"mesas": 0, "quiebras": 0, "neto": 0, "manos": 0, "timeouts": 0})
                d["mesas"] += 1
                d["quiebras"] += j["despues"] == 0
                d["neto"] += j["despues"] - j["antes"]
                d["manos"] += j["manos"]
                d["timeouts"] += j["timeouts"]
    out["por_tipo_mesa"] = {t: {c: {**d, "tasa_quiebra": d["quiebras"] / d["mesas"], "ic": wilson(d["quiebras"], d["mesas"]),
                                    "bb100": 100.0 * d["neto"] / BB / d["manos"] if d["manos"] else float("nan")}
                                for c, d in cs.items()} for t, cs in q.items()}
    tipos = {}
    for r in registros:
        for t, d in r["por_tipo"].items():
            a = tipos.setdefault(t, {"n": 0, "sobrevive": 0, "top6": 0})
            a["n"] += d["n"]
            a["sobrevive"] += d["sobrevive"]
            a["top6"] += d["top6"]
    out["por_tipo_campeonato"] = {t: {**a, "p_sobrevivir": a["sobrevive"] / a["n"], "p_top6": a["top6"] / a["n"]} for t, a in tipos.items()}
    # bb/100 de Bender agrupado por campeonato (para un IC honesto)
    por_t = []
    for r in registros:
        neto = sum(j["despues"] - j["antes"] for j in r["jugadas"] if j.get("tipo") == "bender")
        manos = sum(j["manos"] for j in r["jugadas"] if j.get("tipo") == "bender")
        por_t.append((neto, manos))
    bb = [100.0 * a / BB / b for a, b in por_t if b > 0]
    out["bb100_bender"] = E.resumen_ic(bb)
    out["indicadores"] = {"semillas": [r["semilla"] for r in registros], "sobrevive": surv, "top6": top6, "puesto": puesto}
    errores = sum(1 for r in registros for j in r["jugadas"] if "error" in j)
    out["mesas_con_error"] = errores
    return out


def imprimir(etiqueta, a, comparar=None, ant=None):
    pc = lambda t: f"{100 * t[0]:.1f} % (IC {100 * t[1]:.1f}-{100 * t[2]:.1f})"
    print(f"\n## Campeonato «{etiqueta}»: {a['torneos']} campeonatos de {a['participantes']} participantes (10 rondas, mesas de 5-6)")
    print(f"- **P(sobrevivir las 10 rondas)** = {pc(a['p_sobrevivir'])}")
    print(f"- **P(top 6)** = {pc(a['p_top6'])}   (azar puro con {a['participantes']} participantes: {100 * 6 / a['participantes']:.1f} %)")
    print(f"- P(terminar con más de 10 000) = {pc(a['p_arriba_10000'])}; puesto medio {a['puesto_medio']:.1f}; fichas medias {a['fichas_medias']:,.0f}")
    m, h, nn = a["bb100_bender"]
    print(f"- bb/100 de Bender (todas las rondas, agrupado por campeonato): {m:+.1f} ±{h:.1f} (n={nn})")
    print(f"- mesas con error del conductor: {a['mesas_con_error']}")
    if ant is not None:
        for clave, nombre in (("sobrevive", "P(sobrevivir)"), ("top6", "P(top 6)"), ("puesto", "puesto medio")):
            xs, ys = a["indicadores"][clave], ant["indicadores"][clave]
            comunes = [i for i, s in enumerate(a["indicadores"]["semillas"]) if s in set(ant["indicadores"]["semillas"])]
            ya = dict(zip(ant["indicadores"]["semillas"], ys))
            xs2 = [xs[i] for i in comunes]
            ys2 = [ya[a["indicadores"]["semillas"][i]] for i in comunes]
            if len(xs2) > 5:
                d, lo, hi = bootstrap_dif(xs2, ys2)
                f = (lambda v: f"{100 * v:+.1f} pts") if clave != "puesto" else (lambda v: f"{v:+.2f}")
                print(f"- vs «{comparar}» emparejado ({len(xs2)} semillas comunes): {nombre} {f(d)} (IC {f(lo)} a {f(hi)})")
    print("\n| tipo | mesas (todas) | quiebra por mesa | IC 95 % | mesas ronda 1 | quiebra ronda 1 | bb/100 | P(sobrevivir) | P(top 6) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for t in sorted(a["por_tipo_mesa"], key=lambda t: (t != "bender", t)):
        d, d1, c = a["por_tipo_mesa"][t]["todas"], a["por_tipo_mesa"][t].get("ronda1", {}), a["por_tipo_campeonato"][t]
        print(f"| {'**bender**' if t == 'bender' else t} | {d['mesas']} | {100 * d['tasa_quiebra']:.1f} % | {100 * d['ic'][0]:.0f}-{100 * d['ic'][1]:.0f} % | "
              f"{d1.get('mesas', 0)} | {100 * d1.get('tasa_quiebra', float('nan')):.1f} % | {d['bb100']:+.0f} | {100 * c['p_sobrevivir']:.1f} % | {100 * c['p_top6']:.1f} % |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--etiqueta", required=True)
    ap.add_argument("--params", default=None, help="JSON de parámetros de Bender (por ejemplo riesgo.utilidad y K)")
    ap.add_argument("--campo", default=",".join(f"{b}:4" for b in E.ENTRENAMIENTO), help="bot:copias,...  (Bender se agrega aparte)")
    ap.add_argument("--final", action="store_true", help="permite los rivales de reserva (darwin, novato)")
    ap.add_argument("--torneos", type=int, default=20)
    ap.add_argument("--semilla-base", type=int, default=7_000_000)
    ap.add_argument("--rondas", type=int, default=10)
    ap.add_argument("--manos", type=int, default=50)
    ap.add_argument("--paralelo", type=int, default=4)
    ap.add_argument("--comparar", default=None)
    ap.add_argument("--bender-v1-dir", default=None, help="carpeta bender/ cuyo main.py usan las copias `bender_v1` (por defecto, el código evaluado con utilidad apagada)")
    ap.add_argument("--solo-agregar", action="store_true", help="no juega: solo lee los campeonatos ya guardados")
    args = ap.parse_args()

    globals()["BENDER_V1_DIR"] = os.path.abspath(args.bender_v1_dir) if args.bender_v1_dir else None
    campo = campo_de(args.campo)
    reserva = [n for n, _ in campo if n in E.RESERVA]
    if reserva and not args.final:
        sys.exit(f"{reserva} son de RESERVA: solo con --final (nunca para elegir parámetros).")
    dir_base = os.path.join(SALIDAS, f"camp-{args.etiqueta}")
    os.makedirs(dir_base, exist_ok=True)
    ruta_params = os.path.join(dir_base, "params-usuario.json")
    base = {}
    if args.params:
        with open(args.params, encoding="utf-8") as f:
            base = json.load(f)
    with open(ruta_params, "w", encoding="utf-8") as f:
        json.dump(base, f)

    semillas = [args.semilla_base + i for i in range(args.torneos)]
    inicio = time.time()
    registros, tiempos = [], []
    if args.solo_agregar:
        for s in semillas:
            ruta = os.path.join(dir_base, f"t{s}", "resultado.json")
            if os.path.exists(ruta):
                registros.append(resumir_torneo(json.load(open(ruta, encoding="utf-8"))))
    else:
        print(f"[campeonato] {len(semillas)} campeonatos (campo {args.campo} + Bender), {args.paralelo} en paralelo...", flush=True)
        with ThreadPoolExecutor(args.paralelo) as pool:
            futuros = [pool.submit(correr_torneo, s, campo, ruta_params, dir_base, args.rondas, args.manos) for s in semillas]
            for i, f in enumerate(futuros):
                res, dt = f.result()
                registros.append(resumir_torneo(res))
                if dt:
                    tiempos.append(dt)
                if (i + 1) % 10 == 0:
                    print(f"[campeonato] {i + 1}/{len(semillas)} listos ({time.time() - inicio:.0f} s)", flush=True)
    if not registros:
        sys.exit("no hay campeonatos que agregar")
    a = agregar(registros)
    a.update({"etiqueta": args.etiqueta, "commit": os.environ.get("BENDER_COMMIT"), "commit_completo": os.environ.get("BENDER_COMMIT_COMPLETO"),
              "referencia": {"nombre": os.environ.get("BENDER_REFERENCIA_NOMBRE"), "commit": os.environ.get("BENDER_REFERENCIA"),
                             "diff_codigo": os.environ.get("BENDER_DIFF_CODIGO")},
              "params": base, "campo": args.campo, "semilla_base": args.semilla_base,
              "segundos_por_campeonato": statistics.fmean(tiempos) if tiempos else None, "tiempo_total_s": time.time() - inicio})
    ant = None
    if args.comparar:
        ant = json.load(open(os.path.join(SALIDAS, "evaluaciones", f"camp-{args.comparar}.json"), encoding="utf-8"))
    ruta_json = os.path.join(SALIDAS, "evaluaciones", f"camp-{args.etiqueta}.json")
    os.makedirs(os.path.dirname(ruta_json), exist_ok=True)
    json.dump(a, open(ruta_json, "w", encoding="utf-8"), indent=1, default=str)
    imprimir(args.etiqueta, a, args.comparar, ant)
    if a["segundos_por_campeonato"]:
        print(f"\n({a['segundos_por_campeonato']:.0f} s por campeonato; total {a['tiempo_total_s']:.0f} s; guardado en {ruta_json})")


if __name__ == "__main__":
    main()
