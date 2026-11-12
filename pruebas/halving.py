#!/usr/bin/env python3
"""Capa 3, paso 1: bandido OFFLINE (successive halving) sobre los parámetros de Bender, con la métrica del campeonato.

Campo (28 participantes): 6 bots de entrenamiento × 4 copias + 3 copias `bender_v1` (v1.2-fix con la utilidad apagada y la
regla de limpers apagada: «equipos fuertes desconocidos») + el candidato. darwin y novato NO se usan.

Ronda 1: 48 configuraciones (hipercubo latino por cada caso de los 2 interruptores) + la base, 12 campeonatos cada una.
Rondas 2, 3 y 4: se queda el mejor tercio (16, 5, 2) y se amplía a 36, 108 y 216 campeonatos acumulados (semillas ANIDADAS: las
de la ronda anterior se reutilizan). Rondas 1-3 se ordenan por PUESTO MEDIO emparejado contra la base (menos ruido que P(top 6));
la ronda 4 y la validación, por P(top 6) emparejado (desempates: P(sobrevivir), bb/100). Validación: las 2 finalistas y la base con
150 campeonatos de semillas NUEVAS. Regla de adopción: solo si el IC 95 % de la diferencia emparejada de P(top 6) excluye el 0 a favor.

Se corre SIEMPRE desde un worktree de un commit fijo:
  bender/.venv/Scripts/python.exe bender/pruebas/evaluar_fijo.py --commit <hash> --script halving.py -- --nombre h1
Es reanudable: los campeonatos ya jugados (resultado.json) no se repiten y la selección se recalcula con los datos guardados.
"""

import argparse
import json
import math
import os
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campeonato as CAMP  # noqa: E402
import evaluar as E  # noqa: E402

CAMPO = "aleatorio:4,conservador:4,base:4,estadistico:4,bandido:4,espia:4,bender_v1:3"
SEMILLA_RONDAS = 8_000_000          # semillas de las rondas 1-4 (anidadas)
SEMILLA_VALID = 9_000_000           # semillas NUEVAS de la validación
ACUMULADOS = [12, 36, 108, 216]     # campeonatos por configuración al final de cada ronda
PASAN = [16, 5, 2]                  # cuántas configuraciones siguen tras las rondas 1, 2 y 3
N_VALID = 150
N_POR_CASO = 12                     # configuraciones aleatorias por cada caso de (allin_profundo_solo_valor, solo_valor_sobre_apuesta)

# Dimensiones continuas: (nombre, mínimo, máximo, escala)
DIMS = [("K", 5000.0, 20000.0, "log"),
        ("olvido", 0.005, 0.05, "log"),            # 1 - lambda  (lambda en [0,95, 0,995])
        ("rho_max", 0.5, 1.0, "lin"),
        ("kappa", 0.5, 2.0, "log"),
        ("s_prior", 10.0, 40.0, "lin"),
        ("tamano_bb", 2.2, 3.0, "lin"),
        ("escala_rangos", 0.85, 1.15, "lin"),
        ("iso_por_limper", 0.5, 1.5, "lin"),
        ("apertura_vs_station", 2.5, 4.0, "lin")]
BASE_TOP_POS = {"UTG": 14.3, "HJ": 18.9, "CO": 25.5, "BTN": 43.3, "SB": 33.0, "BTN_SB_HU": 70.0}


def valor(u, lo, hi, escala):
    return math.exp(math.log(lo) + u * (math.log(hi) - math.log(lo))) if escala == "log" else lo + u * (hi - lo)


def variante(x, flags):
    """JSON de parámetros (se mezcla con los de params.py) de una configuración."""
    s = int(round(x["s_prior"]))
    return {"riesgo": {"K": round(x["K"])},
            "olvido": {"lambda": round(1.0 - x["olvido"], 5)},
            "explotacion": {"rho_max": round(x["rho_max"], 4), "kappa": round(x["kappa"], 4)},
            "beta": {"s": {"vpip": s, "pfr": s, "sigue_chica": s, "sigue_grande": s}},
            "apertura": {"tamano_bb": round(x["tamano_bb"], 3), "iso_por_limper": round(x["iso_por_limper"], 3),
                         "apertura_vs_station": round(x["apertura_vs_station"], 3),
                         "top_pos": {k: round(min(100.0, v * x["escala_rangos"]), 2) for k, v in BASE_TOP_POS.items()}},
            "decision": {"allin_profundo_solo_valor": flags[0], "solo_valor_sobre_apuesta": flags[1]}}


def muestrear(semilla=20261112):
    """48 configuraciones: 4 casos de interruptores × 12 puntos de un hipercubo latino en las 9 dimensiones continuas."""
    rng = random.Random(semilla)
    out = []
    for caso, flags in enumerate([(True, True), (True, False), (False, True), (False, False)]):
        perms = []
        for _ in DIMS:
            p = list(range(N_POR_CASO))
            rng.shuffle(p)
            perms.append(p)
        for i in range(N_POR_CASO):
            x = {nombre: valor((perms[d][i] + rng.random()) / N_POR_CASO, lo, hi, esc) for d, (nombre, lo, hi, esc) in enumerate(DIMS)}
            out.append({"id": f"c{caso * N_POR_CASO + i + 1:02d}", "x": x, "flags": list(flags), "variante": variante(x, flags)})
    return out


# --- Ejecución y lectura ---------------------------------------------------------------------------------------------

class Corredor:
    def __init__(self, directorio, paralelo):
        self.dir = directorio
        self.paralelo = paralelo
        self.campo = CAMP.campo_de(CAMPO)
        os.makedirs(os.path.join(directorio, "cfg"), exist_ok=True)
        self.hechos = 0
        self.t0 = time.time()

    def ruta_params(self, cfg):
        ruta = os.path.join(self.dir, "cfg", cfg["id"] + ".json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(cfg["variante"], f, indent=1)
        return ruta

    def dir_cfg(self, cfg, bloque):
        return os.path.join(self.dir, "runs", f"{bloque}-{cfg['id']}")

    def jugar(self, configs, semillas, bloque, etiqueta):
        """Juega (config × semilla) en paralelo, por semilla, de modo que si se corta quedan pares completos."""
        trabajos = [(cfg, s) for s in semillas for cfg in configs]
        pendientes = [t for t in trabajos if not os.path.exists(os.path.join(self.dir_cfg(t[0], bloque), f"t{t[1]}", "resultado.json"))]
        print(f"[halving] {etiqueta}: {len(trabajos)} campeonatos ({len(pendientes)} por jugar)", flush=True)
        rutas = {cfg["id"]: self.ruta_params(cfg) for cfg in configs}

        def uno(t):
            cfg, s = t
            for intento in (1, 2):               # un fallo suelto del conductor no debe tumbar 6 horas de corrida
                try:
                    return CAMP.correr_torneo(s, self.campo, rutas[cfg["id"]], self.dir_cfg(cfg, bloque), 10, 50)
                except Exception as e:           # noqa: BLE001
                    print(f"[halving] campeonato {cfg['id']} semilla {s} falló (intento {intento}): {str(e)[:200]}", flush=True)
            return None

        t_ini, n = time.time(), 0
        with ThreadPoolExecutor(self.paralelo) as pool:
            for _ in pool.map(uno, pendientes):
                n += 1
                if n % 20 == 0 or n == len(pendientes):
                    dt = time.time() - t_ini
                    print(f"[halving] {etiqueta}: {n}/{len(pendientes)} ({dt / 60:.1f} min; quedan ~{dt / n * (len(pendientes) - n) / 60:.0f} min)", flush=True)

    def leer(self, cfg, bloque, semillas):
        """{semilla: (puesto, top6, sobrevive, bb100)} de Bender en cada campeonato jugado."""
        out = {}
        for s in semillas:
            ruta = os.path.join(self.dir_cfg(cfg, bloque), f"t{s}", "resultado.json")
            if not os.path.exists(ruta):
                continue
            res = json.load(open(ruta, encoding="utf-8"))
            reg = CAMP.resumir_torneo(res)
            b = reg["bender"]
            js = [j for j in reg["jugadas"] if j.get("tipo") == "bender"]
            manos = sum(j["manos"] for j in js)
            neto = sum(j["despues"] - j["antes"] for j in js)
            out[s] = (b["puesto"], 1.0 if b["puesto"] <= 6 else 0.0, 1.0 if b["eliminado_en"] == 0 else 0.0,
                      100.0 * neto / CAMP.BB / manos if manos else 0.0)
        return out


# --- Estadística emparejada ------------------------------------------------------------------------------------------

def emparejar(a, base):
    """Listas de diferencias (config − base) por métrica, sobre las semillas comunes."""
    comunes = sorted(set(a) & set(base))
    return {"n": len(comunes), "semillas": comunes,
            **{m: [a[s][i] - base[s][i] for s in comunes] for i, m in enumerate(("puesto", "top6", "sobrevive", "bb100"))}}


def ic(d, B=4000, semilla=3):
    if len(d) < 5:
        return (statistics.fmean(d) if d else float("nan"), float("nan"), float("nan"))
    rng = random.Random(semilla)
    ms = sorted(statistics.fmean(rng.choices(d, k=len(d))) for _ in range(B))
    return statistics.fmean(d), ms[int(0.025 * B)], ms[int(0.975 * B)]


# --- Importancia de parámetros (OLS sobre la ronda 1) ------------------------------------------------------------------

def ols(X, y):
    """Mínimos cuadrados con intercepto. Devuelve (coeficientes, errores estándar) o None si es singular."""
    n, p = len(X), len(X[0]) + 1
    A = [[1.0] + list(r) for r in X]
    M = [[sum(A[k][i] * A[k][j] for k in range(n)) for j in range(p)] for i in range(p)]
    v = [sum(A[k][i] * y[k] for k in range(n)) for i in range(p)]
    aug = [M[i][:] + [1.0 if i == j else 0.0 for j in range(p)] + [v[i]] for i in range(p)]
    for c in range(p):
        piv = max(range(c, p), key=lambda r: abs(aug[r][c]))
        if abs(aug[piv][c]) < 1e-12:
            return None
        aug[c], aug[piv] = aug[piv], aug[c]
        f = aug[c][c]
        aug[c] = [z / f for z in aug[c]]
        for r in range(p):
            if r != c:
                g = aug[r][c]
                aug[r] = [z - g * w for z, w in zip(aug[r], aug[c])]
    beta = [aug[i][-1] for i in range(p)]
    inv = [row[p:2 * p] for row in aug]
    resid = [y[k] - sum(A[k][j] * beta[j] for j in range(p)) for k in range(n)]
    s2 = sum(e * e for e in resid) / max(1, n - p)
    return beta, [math.sqrt(max(0.0, s2 * inv[i][i])) for i in range(p)]


def importancia(configs, delta_por_cfg):
    """Regresión de Δ puesto medio (config − base, ronda 1) sobre los parámetros llevados a [-1, 1]."""
    nombres = [d[0] for d in DIMS] + ["allin_profundo_solo_valor", "solo_valor_sobre_apuesta"]
    X, y = [], []
    for cfg in configs:
        if cfg["id"] not in delta_por_cfg:
            continue
        fila = []
        for nombre, lo, hi, esc in DIMS:
            v = cfg["x"][nombre]
            u = (math.log(v) - math.log(lo)) / (math.log(hi) - math.log(lo)) if esc == "log" else (v - lo) / (hi - lo)
            fila.append(2 * u - 1)
        fila += [1.0 if f else -1.0 for f in cfg["flags"]]
        X.append(fila)
        y.append(delta_por_cfg[cfg["id"]])
    r = ols(X, y)
    if r is None:
        return None
    beta, se = r
    return sorted(((nombres[i], beta[i + 1], se[i + 1], beta[i + 1] / se[i + 1] if se[i + 1] else float("nan")) for i in range(len(nombres))),
                  key=lambda t: -abs(t[3]))


# --- Programa principal ------------------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nombre", default="h1")
    ap.add_argument("--paralelo", type=int, default=10)
    ap.add_argument("--solo-informe", action="store_true", help="no juega: arma el informe con lo ya guardado")
    ap.add_argument("--humo", action="store_true", help="prueba de punta a punta en miniatura (6 configuraciones, 1-2-3-4 campeonatos, validación de 2)")
    args = ap.parse_args()
    if args.humo:
        globals().update(ACUMULADOS=[1, 2, 3, 4], PASAN=[4, 3, 2], N_VALID=2)
    directorio = os.path.join(E.SALIDAS, "halving", args.nombre)
    os.makedirs(directorio, exist_ok=True)
    cor = Corredor(directorio, args.paralelo)
    base = {"id": "base", "x": None, "flags": None, "variante": {}}
    configs = muestrear()[::8] if args.humo else muestrear()       # humo: 6 configuraciones repartidas entre los 4 casos
    json.dump({"commit": os.environ.get("BENDER_COMMIT_COMPLETO"), "campo": CAMPO, "acumulados": ACUMULADOS, "pasan": PASAN,
              "configuraciones": configs}, open(os.path.join(directorio, "configuraciones.json"), "w"), indent=1)
    sem = [SEMILLA_RONDAS + i for i in range(ACUMULADOS[-1])]
    vivas, hist = list(configs), []
    t_inicio = time.time()

    def datos(cfg, hasta):
        return cor.leer(cfg, "r", sem[:hasta])

    for r, hasta in enumerate(ACUMULADOS[:-1] + [ACUMULADOS[-1]]):
        desde = 0 if r == 0 else ACUMULADOS[r - 1]
        if not args.solo_informe:
            cor.jugar([base] + vivas, sem[desde:hasta], "r", f"ronda {r + 1} ({len(vivas)}+base × {hasta - desde} nuevos)")
        base_d = datos(base, hasta)
        filas = []
        for cfg in vivas:
            d = emparejar(datos(cfg, hasta), base_d)
            if d["n"] == 0:
                continue
            filas.append({"id": cfg["id"], "n": d["n"], "d_puesto": statistics.fmean(d["puesto"]), "d_top6": statistics.fmean(d["top6"]),
                          "d_surv": statistics.fmean(d["sobrevive"]), "d_bb100": statistics.fmean(d["bb100"])})
        if r < 3:
            filas.sort(key=lambda f: f["d_puesto"])                        # rondas 1-3: puesto medio (menor = mejor)
        else:
            filas.sort(key=lambda f: (-f["d_top6"], -f["d_surv"], -f["d_bb100"]))    # ronda 4: P(top 6), P(sobrevivir), bb/100
        hist.append({"ronda": r + 1, "acumulados": hasta, "ranking": filas})
        if r == 0:
            delta_r1 = {f["id"]: f["d_puesto"] for f in filas}
        if r < 3:
            vivas = [c for c in vivas if c["id"] in {f["id"] for f in filas[:PASAN[r]]}]
            print(f"[halving] ronda {r + 1}: pasan {[c['id'] for c in vivas]}", flush=True)
    finalistas = vivas
    json.dump({"historia": hist}, open(os.path.join(directorio, "historia.json"), "w"), indent=1)

    # --- validación con semillas NUEVAS ---
    sem_v = [SEMILLA_VALID + i for i in range(N_VALID)]
    if not args.solo_informe:
        cor.jugar([base] + finalistas, sem_v, "v", f"validación ({len(finalistas)}+base × {N_VALID} semillas nuevas)")
    base_v = cor.leer(base, "v", sem_v)
    val = []
    for cfg in finalistas:
        d = emparejar(cor.leer(cfg, "v", sem_v), base_v)
        val.append({"cfg": cfg, "n": d["n"], **{m: ic(d[m]) for m in ("top6", "sobrevive", "puesto", "bb100")}})
    val.sort(key=lambda v: (-v["top6"][0], -v["sobrevive"][0], -v["bb100"][0]))

    # --- informe ---
    L = []
    L.append(f"# Halving «{args.nombre}» (commit {os.environ.get('BENDER_COMMIT')}; campo {CAMPO} + candidato; {(time.time() - t_inicio) / 3600:.1f} h en esta corrida)\n")
    for h in hist:
        L.append(f"## Ronda {h['ronda']} ({h['acumulados']} campeonatos acumulados): Δ contra la base, emparejado\n")
        L.append("| config | n | Δ puesto medio | Δ P(top 6) pts | Δ P(sobrevivir) pts | Δ bb/100 |")
        L.append("|---|---|---|---|---|---|")
        for f in h["ranking"][:(PASAN[h["ronda"] - 1] + 4 if h["ronda"] <= 3 else 3)]:
            L.append(f"| {f['id']} | {f['n']} | {f['d_puesto']:+.2f} | {100 * f['d_top6']:+.1f} | {100 * f['d_surv']:+.1f} | {f['d_bb100']:+.0f} |")
        L.append("")
    L.append(f"## Validación con {N_VALID} campeonatos de semillas NUEVAS (emparejado contra la base)\n")
    L.append("| finalista | Δ P(top 6) pts (IC 95 %) | Δ P(sobrevivir) pts (IC 95 %) | Δ puesto medio (IC 95 %) | Δ bb/100 (IC 95 %) | ¿gana? |")
    L.append("|---|---|---|---|---|---|")
    ganadoras = []
    for v in val:
        t, s, p, b = v["top6"], v["sobrevive"], v["puesto"], v["bb100"]
        gana = t[1] > 0                                    # el IC 95 % excluye el 0 a favor
        if gana:
            ganadoras.append(v)
        L.append(f"| {v['cfg']['id']} | {100 * t[0]:+.1f} ({100 * t[1]:+.1f} a {100 * t[2]:+.1f}) | {100 * s[0]:+.1f} ({100 * s[1]:+.1f} a {100 * s[2]:+.1f}) | "
                 f"{p[0]:+.2f} ({p[1]:+.2f} a {p[2]:+.2f}) | {b[0]:+.0f} ({b[1]:+.0f} a {b[2]:+.0f}) | {'SÍ' if gana else 'no'} |")
    L.append("")
    if ganadoras:
        v = ganadoras[0]
        L.append(f"**Hay finalista que gana con IC que excluye el 0: {v['cfg']['id']}.** Variante lista para aplicar (NO aplicada a los valores por defecto):\n")
        L.append("```json\n" + json.dumps(v["cfg"]["variante"], indent=1) + "\n```")
    else:
        L.append("**Ninguna finalista le gana a la base con IC 95 % que excluya el 0: no se cambian los valores por defecto.**")
    L.append("\n## Finalistas: parámetros\n")
    for v in val:
        L.append(f"- {v['cfg']['id']}: flags (allin_profundo_solo_valor, solo_valor_sobre_apuesta) = {v['cfg']['flags']}; " +
                 ", ".join(f"{k}={x:.3g}" for k, x in v["cfg"]["x"].items()))
    imp = importancia(configs, delta_r1)
    L.append("\n## Importancia de parámetros (indicio): regresión de Δ puesto medio de la ronda 1 (12 campeonatos × 48 configuraciones) sobre los parámetros en [-1, 1]\n")
    if imp:
        L.append("Coeficiente = cambio del puesto medio al pasar del mínimo al máximo del rango (÷ 2 por unidad); negativo = mejora. |t| > 2 sería «suficiente» con un solo contraste, pero aquí hay 11 y solo 48 puntos ruidosos: es un indicio.\n")
        L.append("| parámetro | coeficiente | error estándar | t |")
        L.append("|---|---|---|---|")
        for nombre, b, se, t in imp:
            L.append(f"| {nombre} | {b:+.3f} | {se:.3f} | {t:+.2f} |")
    texto = "\n".join(L)
    open(os.path.join(directorio, "informe.md"), "w", encoding="utf-8").write(texto)
    print(texto)


if __name__ == "__main__":
    main()
