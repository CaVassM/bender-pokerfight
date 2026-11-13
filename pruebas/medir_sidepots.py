#!/usr/bin/env python3
"""Mide cuánto dinero hay en botes laterales (side pots) en las decisiones de Bender y cuánto EV está en juego.

El modelo de EV de Bender (§1.9, §1.11) valora el bote entero con una sola equity e' contra TODOS los que siguen, incluidos los rivales
all-in. No modela botes laterales: si un rival all-in (con menos fichas) pone un tope al bote principal, lo que ponen los demás por
encima de ese tope es un bote lateral que ese rival no puede ganar. Eso se mide aquí con las PILAS REALES de los mensajes crudos:

  - S⁰ de cada jugador al empezar la mano (saldo + apuesta de ronda en el `mano_inicio`) y lo que ya puso (S⁰ − saldo) en cada decisión.
  - Para la acción ELEGIDA (igualar, apostar, subir o all-in) se arma el bote al que llega Bender (P + lo que agrega Bender + lo que agrega el
    pagador del modelo, A') y se reparte: bote principal = Σ_i min(aporte_i, aporte del all-in más corto) y bote lateral = el resto.
  - EV en juego = dinero lateral × gap, con gap = diferencia entre la equity de Bender solo contra los que disputan el lateral y la e' del
    modelo contra todos. No se mide el gap (no hay las equities por rival en el log): se muestran gap = 5, 10 y 20 puntos de equity.

Corre N campeonatos del campo de entrenamiento con los parámetros por defecto y los mensajes crudos encendidos (BENDER_MENSAJES=1):
  bender/.venv/Scripts/python.exe bender/pruebas/evaluar_fijo.py --script medir_sidepots.py -- --n 60
"""

import argparse
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
BB = 100


def decisiones_lateral(ruta):
    """(manos de Bender, lista de decisiones con rival all-in y sus botes). Lee los `msg` y los `decision` del log."""
    manos, s0, ultimo, out, mi_id = 0, {}, None, [], None
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            if '"tipo":"conexion"' in linea and '"tipo":"msg"' not in linea:
                mi_id = json.loads(linea).get("id_jugador")
            elif '"tipo":"msg"' in linea:
                r = json.loads(linea)["msg"]
                if r.get("tipo") == "mano_inicio":
                    manos += 1
                    s0 = {j["id"]: j["saldo"] + j.get("apuesta_ronda", 0) for j in (r.get("estado") or {}).get("jugadores", []) if j.get("en_mano")}
                elif r.get("tipo") == "solicitar_accion":
                    ultimo = r.get("estado") or {}
            elif '"tipo":"decision"' in linea and ultimo is not None:
                d = json.loads(linea)
                if d.get("tipo") == "decision":
                    a = lateral(d, ultimo, s0, mi_id)
                    if a:
                        out.append(a)
    return manos, out


def lateral(d, estado, s0, mi_id):
    """Dict con el bote principal/lateral de la acción elegida, o None si no hay rival all-in disputando o la acción es retirarse."""
    acc = d["accion"]["tipo"]
    if acc in ("fold", "check"):
        return None
    jug = estado.get("jugadores", [])
    mi = next((j for j in jug if j["id"] == mi_id and j.get("activo") and j["id"] in s0 and not j.get("allin")), None)
    activos = [j for j in jug if j.get("activo") and j["id"] in s0]
    allins = [j for j in activos if j.get("allin") and mi is not None and j["id"] != mi["id"]]
    responden = [j for j in activos if not j.get("allin") and mi is not None and j["id"] != mi["id"]]
    if mi is None or not allins or not responden:
        return None
    aporte = {j["id"]: s0[j["id"]] - j["saldo"] for j in jug if j["id"] in s0}          # lo puesto en esta mano hasta ahora
    elegida = next((f for f in d["info"].get("tabla_ev", []) if f["tipo"] == acc and f.get("monto") == d["accion"].get("monto")), None) \
        or next((f for f in d["info"].get("tabla_ev", []) if f["tipo"] == acc), None)
    if acc == "call":
        agrega_yo, agrega_pagador = d["C"], 0
    elif elegida is not None and "A" in elegida:
        agrega_yo, agrega_pagador = elegida["A"], elegida.get("A_prima", 0)
    else:
        return None
    final = dict(aporte)
    final[mi["id"]] = aporte[mi["id"]] + agrega_yo
    grande = max(responden, key=lambda j: j["saldo"] + j.get("apuesta_ronda", 0))
    final[grande["id"]] = aporte[grande["id"]] + agrega_pagador
    tope = min(final[j["id"]] for j in allins)                                           # el all-in más corto manda el bote principal
    pot_final = d["P"] + agrega_yo + agrega_pagador
    principal = sum(min(v, tope) for v in final.values())
    lat = max(0, pot_final - principal)
    disputan = [j for j in responden if final[j["id"]] > tope] + ([mi] if final[mi["id"]] > tope else [])
    return {"calle": d["etapa"], "accion": acc, "P": d["P"], "pot_final": pot_final, "lateral": lat, "n_disputan_lateral": len(disputan),
            "n_allin": len(allins), "n_responden": len(responden)}


def informe(manos, filas, n_camp):
    por100 = lambda x: 100.0 * x / manos if manos else float("nan")
    L = [f"# Side pots en {n_camp} campeonatos con mensajes crudos: {manos} manos de Bender, {len(filas)} decisiones con rival all-in y alguien más en la mano "
         f"(acción elegida distinta de retirarse/pasar)\n"]
    con = [f for f in filas if f["lateral"] > 0 and f["n_disputan_lateral"] >= 2]
    L.append(f"- Decisiones con algún rival all-in y un respondedor más: {len(filas)} = {por100(len(filas)):.2f} por 100 manos.")
    L.append(f"- De ellas, con bote lateral REAL disputado por Bender y al menos otro jugador: {len(con)} = {por100(len(con)):.2f} por 100 manos "
             f"({100 * len(con) / max(1, len(filas)):.0f} % de las anteriores).")
    if con:
        lat = sum(f["lateral"] for f in con) / BB
        L.append(f"- Dinero en bote lateral en esas decisiones: media {lat / len(con):.1f} bb por decisión "
                 f"({100 * sum(f['lateral'] / f['pot_final'] for f in con) / len(con):.0f} % del bote final); total {por100(lat):.2f} bb por 100 manos.")
        L.append("\n| gap de equity supuesto (lateral vs modelo) | EV en juego (bb/100 manos) |\n|---|---|")
        for g in (0.05, 0.10, 0.20):
            L.append(f"| {int(100 * g)} puntos | {por100(lat * g):.2f} |")
        por = {}
        for f in con:
            por.setdefault(f["calle"], []).append(f)
        L.append("\n| calle | decisiones | por 100 manos | lateral medio (bb) |\n|---|---|---|---|")
        for c in ("preflop", "flop", "turn", "river"):
            if c in por:
                L.append(f"| {c} | {len(por[c])} | {por100(len(por[c])):.2f} | {sum(f['lateral'] for f in por[c]) / len(por[c]) / BB:.1f} |")
    L.append("\nEl gap no se mide: hace falta la equity de Bender solo contra quienes disputan el lateral, que el log no trae. "
             "Con un gap de 10 puntos (lo típico entre jugar contra uno o contra todos) se ve el orden de magnitud.")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--semilla0", type=int, default=12_000_000)
    ap.add_argument("--paralelo", type=int, default=10)
    ap.add_argument("--nombre", default="sidepots")
    ap.add_argument("--solo-informe", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    os.environ["BENDER_MENSAJES"] = "1"                           # campeonato.correr_torneo respeta esta variable
    import evaluar as E
    import halving as H
    directorio = os.path.join(E.SALIDAS, args.nombre)
    os.makedirs(directorio, exist_ok=True)
    cor = H.Corredor(directorio, args.paralelo)
    cfg = {"id": "base", "variante": {}}
    sem = [args.semilla0 + i for i in range(args.n)]
    if not args.solo_informe:
        cor.jugar([cfg], sem, "m", f"side pots: {args.n} campeonatos con mensajes crudos")
    manos, filas, n = 0, [], 0
    for s in sem:
        ruta = os.path.join(cor.dir_cfg(cfg, "m"), f"t{s}", "bender.jsonl")
        if os.path.exists(ruta):
            m, f = decisiones_lateral(ruta)
            manos, n = manos + m, n + 1
            filas += f
    texto = informe(manos, filas, n)
    open(os.path.join(directorio, "informe.md"), "w", encoding="utf-8").write(texto)
    print(texto)


if __name__ == "__main__":
    main()
