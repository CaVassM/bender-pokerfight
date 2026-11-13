#!/usr/bin/env python3
"""Mide en los logs de decisión de Bender (bender.jsonl de campeonatos ya jugados) cuánto pesa el sesgo conocido de A' en el EV
de las apuestas con varios respondedores («multiway») y con rivales all-in (side pots, que no se modelan).

Qué mide (no cambia ninguna decisión; solo lee):
 1. Frecuencia: decisiones por cada 100 manos con apuesta/subida/all-in disponible, por calle y número de respondedores.
 2. Sesgo de A': el modelo usa A' = lo que pone UN solo pagador (el mayor). Si pagan k rivales el bote al que se llega es
    P + A + (suma de lo que ponen los pagadores). Con los logs no están las pilas de los rivales, así que se usa la COTA SUPERIOR del
    sesgo: A'_corr = A'·E[k | k>=1], con E[k | k>=1] = Σc_i/(1−f) (cada pagador pone A' como máximo). Se recalcula la utilidad (§1.13)
    de cada apuesta con A'_corr (misma fórmula del bot) y se ve (a) cuántas veces cambiaría la acción elegida y (b) cuántas fichas
    (equivalente cierto) se pierden en promedio: el «EV en juego» en bb/100 si el bote verdadero fuera ese.
 3. Side pots (proxy): decisiones con algún rival all-in y al menos un respondedor: ahí el bote tiene botes laterales que el modelo
    ignora. Sin las pilas de los rivales solo se puede contar la frecuencia y el tamaño del bote P en esas decisiones.

Uso: bender/.venv/Scripts/python.exe bender/pruebas/medir_multiway.py --bloque v-base --semilla0 9000000 --n 150
"""

import argparse
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, AQUI)
import capa1 as C1  # noqa: E402
import evaluar as E  # noqa: E402

BB = 100


def decisiones(ruta):
    manos, out = 0, []
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            if '"mano_inicio"' in linea:
                manos += 1
            elif '"decision"' in linea:
                r = json.loads(linea)
                if r.get("tipo") == "decision" and "tabla_ev" in r.get("info", {}):
                    out.append(r)
    return manos, out


def analizar_decision(d):
    """None si no hay apuesta evaluada; si no, un dict con la comparación base / corregido."""
    info = d["info"]
    filas = info["tabla_ev"]
    apuestas = [f for f in filas if "A_prima" in f]
    if not apuestas:
        return None
    n_resp = len(apuestas[0]["c"])
    S, K, P = d["saldo"], info["utilidad"]["K"], d["P"]
    rivales = d["rivales"]
    base, corr = [], []
    for f in filas:
        if f["descartada"]:
            continue
        if "A_prima" in f and f["accion"] != "iso-raise":      # el iso-raise ya suma a todos los pagadores (§1.5): no se corrige
            f_, c = f["f"], f["c"]
            k_cond = min(float(len(c)), sum(c.values()) / max(1e-9, 1.0 - f_))
            k_cond = max(1.0, k_cond)
            u2 = C1.u_apuesta(f_, P, f["e_prima"], f["A"], f["A_prima"] * k_cond, S, K)
            ce2 = C1.equivalente_cierto(u2, S, K)
        else:
            ce2 = f["ce"]
        base.append((f["ce"], f["accion"], f.get("tipo"), ce2))
        corr.append((ce2, f["accion"], f.get("tipo")))
    if not base:
        return None
    elegida_base = max(base, key=lambda t: t[0])
    elegida_corr = max(corr, key=lambda t: t[0])
    # EV en juego: cuánto vale (con el bote corregido) la mejor acción corregida frente a la que elige hoy el bot
    perdida = elegida_corr[0] - next(t[3] for t in base if t[1] == elegida_base[1])
    return {"calle": d["etapa"], "n_resp": n_resp, "allin_riv": max(0, rivales - n_resp), "P": P,
            "elige_apuesta": elegida_base[2] in ("bet", "raise", "allin"), "cambia": elegida_corr[1] != elegida_base[1],
            "perdida": max(0.0, perdida), "mejora_a_apuesta": elegida_corr[2] in ("bet", "raise", "allin")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--directorio", default="h1")
    ap.add_argument("--fuentes", default="v-base:9000000:150,r-base:8000000:216",
                    help="bloque:semilla0:n separados por coma (carpetas runs/<bloque>/t<semilla>); por defecto la base de h1 (v1.3-limpers)")
    ap.add_argument("--salida", default="medir-multiway")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    manos, filas, n_camp = 0, [], 0
    for fuente in args.fuentes.split(","):
        bloque, semilla0, n = fuente.split(":")
        base = os.path.join(E.SALIDAS, "halving", args.directorio, "runs", bloque)
        for i in range(int(n)):
            ruta = os.path.join(base, f"t{int(semilla0) + i}", "bender.jsonl")
            if not os.path.exists(ruta):
                continue
            m, ds = decisiones(ruta)
            manos += m
            n_camp += 1
            filas += [a for a in (analizar_decision(d) for d in ds) if a]
    L = [f"# Sesgo de A' multiway y side pots — {n_camp} campeonatos de «{args.directorio}» ({args.fuentes}), {manos} manos de Bender, "
         f"{len(filas)} decisiones con apuesta evaluada\n"]
    por100 = lambda n: 100.0 * n / manos if manos else float("nan")

    L.append("## 1. Frecuencia de decisiones con apuesta/subida/all-in en el menú (por 100 manos de Bender)\n")
    L.append("| calle | respondedores | decisiones /100 manos | % de las decisiones con apuesta |")
    L.append("|---|---|---|---|")
    for calle in ("preflop", "flop", "turn", "river"):
        for nr in (1, 2, 3, 4):
            sel = [f for f in filas if f["calle"] == calle and (f["n_resp"] == nr if nr < 4 else f["n_resp"] >= 4)]
            if sel:
                L.append(f"| {calle} | {nr if nr < 4 else '4+'} | {por100(len(sel)):.1f} | {100 * len(sel) / len(filas):.1f} % |")
    multi = [f for f in filas if f["n_resp"] >= 2]
    L.append(f"\nMultiway (≥ 2 respondedores): {len(multi)} decisiones = {100 * len(multi) / len(filas):.1f} % de las que tienen apuesta; {por100(len(multi)):.1f} por 100 manos.\n")

    L.append("## 2. Sesgo de A' (cota superior): ¿cambia la acción y cuánto vale?\n")
    L.append("Pérdida = (equivalente cierto de la mejor acción con A' corregido) − (el de la acción que elige hoy el bot, también corregido), en fichas; 100 fichas = 1 bb.\n")
    L.append("| grupo | decisiones | % que cambia la acción | de ellas: pasan a apostar | pérdida media por decisión (bb) | EV en juego (bb/100 manos) |")
    L.append("|---|---|---|---|---|---|")
    grupos = [("1 respondedor (A' exacto)", lambda f: f["n_resp"] == 1),
              ("multiway ≥ 2, flop/turn/river", lambda f: f["n_resp"] >= 2 and f["calle"] != "preflop"),
              ("multiway ≥ 2, preflop", lambda f: f["n_resp"] >= 2 and f["calle"] == "preflop"),
              ("todos", lambda f: True)]
    for nombre, fn in grupos:
        sel = [f for f in filas if fn(f)]
        if not sel:
            continue
        cam = [f for f in sel if f["cambia"]]
        perd = sum(f["perdida"] for f in sel)
        L.append(f"| {nombre} | {len(sel)} | {100 * len(cam) / len(sel):.1f} % | {sum(1 for f in cam if f['mejora_a_apuesta'])} | "
                 f"{perd / len(sel) / BB:.3f} | {perd / BB * 100.0 / manos:.2f} |")
    L.append("")
    sel = [f for f in multi if f["calle"] != "preflop"]
    if sel:
        con = sorted(f["perdida"] for f in sel if f["perdida"] > 0)
        if con:
            L.append(f"Multiway postflop: solo el {100 * len(con) / len(sel):.1f} % de las decisiones tiene pérdida > 0; cuando la hay, la mediana es "
                     f"{con[len(con) // 2] / BB:.2f} bb y el máximo {con[-1] / BB:.1f} bb.\n")

    L.append("## 3. Side pots (proxy): decisiones con algún rival all-in y al menos un respondedor\n")
    sp = [f for f in filas if f["allin_riv"] >= 1]
    L.append(f"- Decisiones con apuesta en el menú y ≥ 1 rival all-in: {len(sp)} = {por100(len(sp)):.2f} por 100 manos "
             f"({100 * len(sp) / len(filas):.1f} % de las que tienen apuesta); bote medio P = {sum(f['P'] for f in sp) / max(1, len(sp)) / BB:.1f} bb.")
    sp2 = [f for f in sp if f["n_resp"] >= 2]
    L.append(f"- Con ≥ 2 respondedores además del all-in (donde el bote lateral se disputa entre varios): {len(sp2)} = {por100(len(sp2)):.2f} por 100 manos.")
    L.append("- El EV en juego de los side pots no se puede estimar con estos logs: no traen las pilas de los rivales.")
    texto = "\n".join(L)
    out = os.path.join(E.SALIDAS, args.salida)
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "informe.md"), "w", encoding="utf-8").write(texto)
    print(texto)


if __name__ == "__main__":
    main()
