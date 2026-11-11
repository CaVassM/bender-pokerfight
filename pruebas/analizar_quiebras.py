#!/usr/bin/env python3
"""Análisis de quiebras de Bender en una corrida de mesas de 5 (evaluar.py --solo-mesa --mensajes).

Lee, de la corrida `<etiqueta>`: el JSON (salidas/evaluaciones/<etiqueta>.json, con `mesa.detalle`) y el log de
Bender de cada mesa (salidas/eval-<etiqueta>/mesa-<i>/bender.jsonl). NO cambia nada de Bender ni vuelve a jugar.

  1. Tasa de quiebra por mesa (Bender termina con 0 fichas) y percentiles del stack final.
  2. Por cada mano en que Bender pierde más del 50 % de su stack: calle, modo, e, e', EV de las opciones, acción,
     stack efectivo en bb, rival(es) y su tipo/bot reconocido, y si la decisión estaba cerca del umbral.
  3. Tabla resumen por tipo de decisión (todas las manos grandes y solo las que dejaron a Bender en 0).
  4. Supervivencia de un torneo de 10 rondas por bootstrap de los resultados por mesa (APROXIMACIÓN).

Definiciones (para que los números se puedan discutir):
  - stack_antes de una mano = saldo + apuesta_ronda de Bender en el `mano_inicio` (ya con su ciega puesta).
    stack_despues = stack_antes de la mano siguiente (la última: las fichas finales de la mesa).
  - mano grande = pérdida > 50 % del stack_antes.
  - inversión de una decisión = fichas que salen del stack en esa decisión (saldo antes − saldo en la siguiente
    decisión de la mano; para la última: saldo − (stack_despues − ganado)).
  - decisión decisiva = la de mayor inversión de la mano (empate: la última).
  - compromiso = inversión >= 90 % del saldo de ese momento (all-in de hecho).
  - margen de EV = (EV de la elegida − mejor EV de las demás opciones no descartadas) / saldo.
  - cerca del umbral: margen de EV < 5 % del saldo; en calls, además e − e_min < 0,05 con e_min = C/(P+C).
"""

import argparse
import csv
import json
import math
import os
import random
import statistics
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evaluar as E  # noqa: E402

BB = E.BB
STACK = E.STACK_MESA
UMBRAL_COMPROMISO = 0.9
UMBRAL_GRANDE = 0.5
CERCA_EV = 0.05
CERCA_E = 0.05


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def percentil(v, p):
    v = sorted(v)
    if not v:
        return float("nan")
    k = (len(v) - 1) * p / 100
    i, f = int(math.floor(k)), k - math.floor(k)
    return v[i] if i + 1 >= len(v) else v[i] * (1 - f) + v[i + 1] * f


# --- Lectura de una mesa ----------------------------------------------------------------------------------------

def leer_mesa(ruta_log, indice, final):
    """Manos de Bender en una mesa: [{id, antes, despues, rivales_ids, decisiones, gane, ganadores}]."""
    mi_id = f"bender-{indice}"
    manos, por_id = [], {}
    for linea in open(ruta_log, encoding="utf-8"):
        cab = linea[:140]
        if '"tipo":"msg","msg":{"tipo":"mano_inicio"' in cab:
            est = json.loads(linea)["msg"]["estado"]
            yo = next((j for j in est["jugadores"] if j["id"] == mi_id), None)
            if yo is None:
                continue
            m = {"id": est["id_mano"], "antes": yo["saldo"] + yo["apuesta_ronda"], "despues": None,
                 "rivales_ids": [j["id"] for j in est["jugadores"] if j["id"] != mi_id and j.get("en_mano")],
                 "decisiones": [], "gane": 0, "ganadores": []}
            manos.append(m)
            por_id[m["id"]] = m
        elif '"tipo":"decision"' in cab[:80]:
            d = json.loads(linea)
            m = por_id.get(d["id_mano"])
            if m is not None:
                m["decisiones"].append(d)
        elif '"tipo":"msg","msg":{"tipo":"mano_fin"' in cab:
            res = json.loads(linea)["msg"].get("resultado") or {}
            m = por_id.get(res.get("id_mano"))
            if m is not None:
                m["ganadores"] = sorted({r["id_jugador"] for r in res.get("repartos", [])})
        elif '"tipo":"mano_fin"' in cab[:80]:
            r = json.loads(linea)
            m = por_id.get(r.get("id_mano"))
            if m is not None:
                m["gane"] = r.get("gane", 0)
    for k, m in enumerate(manos):
        m["despues"] = manos[k + 1]["antes"] if k + 1 < len(manos) else final
    return manos


def inversiones(m):
    ds = sorted(m["decisiones"], key=lambda d: d["n"])
    out = []
    for k, d in enumerate(ds):
        if k + 1 < len(ds):
            inv = d["saldo"] - ds[k + 1]["saldo"]
        else:
            inv = d["saldo"] - (m["despues"] - m["gane"])
        out.append(max(0, inv))
    return ds, out


# --- Descripción de la decisión decisiva ----------------------------------------------------------------------

def opcion_elegida(info, accion):
    """(e', EV) de la opción que se jugó, de `info.elegida` o buscando en tabla_ev por tipo/monto."""
    eleg = info.get("elegida")
    tabla = info.get("tabla_ev") or []
    if isinstance(eleg, dict) and "ev" in eleg:
        return eleg.get("e_prima"), eleg.get("ev"), eleg
    if isinstance(eleg, int) and 0 <= eleg < len(tabla):
        t = tabla[eleg]
        return t.get("e_prima"), t.get("ev"), t
    cand = [t for t in tabla if t.get("tipo") == accion.get("tipo") and not t.get("descartada")]
    if accion.get("monto") is not None:
        mejor = [t for t in cand if t.get("monto") == accion.get("monto")]
        cand = mejor or cand
    if cand:
        t = cand[0]
        return t.get("e_prima"), t.get("ev"), t
    return None, None, None


def describir(m, d, inv):
    info = d.get("info") or {}
    acc = d["accion"]
    e_prima, ev_elegida, ent = opcion_elegida(info, acc)
    ent = ent or {}
    tabla = info.get("tabla_ev") or []
    otras = [t["ev"] for t in tabla if t.get("ev") is not None and not t.get("descartada")
             and t.get("ev") != ev_elegida]
    mejor_otra = max(otras) if otras else None
    saldo = d["saldo"]
    e = (info.get("equity") or {}).get("e")
    P, C = d.get("P") or 0, d.get("C") or 0
    e_min = C / (P + C) if (P + C) > 0 and C > 0 else None
    margen = (ev_elegida - mejor_otra) / saldo if (ev_elegida is not None and mejor_otra is not None and saldo) else None
    riv = info.get("rivales") or {}
    rivales = []
    for rid, r in riv.items():
        real = rid[2:] if rid.startswith("k-") else rid
        bot = r.get("bot") or [None, None]
        rivales.append({"id": rid, "real": real, "tipo": r.get("tipo"), "bot": bot[0], "p_bot": bot[1]})
    return {"etapa": d["etapa"], "modo": info.get("modo"), "decision": info.get("decision"), "accion": acc.get("tipo"),
            "motivo": d.get("motivo"), "saldo": saldo, "s_ef_bb": d.get("s_ef_bb"), "inversion": inv, "P": P, "C": C,
            "e": e, "e_prima": e_prima, "e_min": e_min, "ev_elegida": ev_elegida, "margen_ev": margen,
            "f": ent.get("f"), "x": ent.get("x"), "A": ent.get("A"),
            # parte del EV que viene de que todos se retiren (f·P) frente a la que viene del showdown si pagan
            "ev_por_fold_pct": (ent["f"] * P / ev_elegida) if (ent.get("f") is not None and ev_elegida and ev_elegida > 0) else None,
            "opciones": [(t.get("accion"), t.get("ev"), bool(t.get("descartada"))) for t in tabla],
            "n_rivales_decision": d.get("rivales"), "rivales": rivales, "cartas": d.get("cartas"), "comunitarias": d.get("mesa"),
            "posicion": d.get("posicion")}


def categoria(desc, hay_decision):
    if not hay_decision:
        return "ciegas (stack mínimo, sin decisión)"
    acc, saldo, inv, modo = desc["accion"], desc["saldo"], desc["inversion"], desc["modo"]
    compromiso = saldo > 0 and inv >= UMBRAL_COMPROMISO * saldo
    if acc == "allin" or (compromiso and acc in ("bet", "raise")):
        return "all-in propio, push/fold (≤15 bb)" if modo == "push_fold" else f"all-in propio, modo {modo}"
    if acc == "call":
        if compromiso:
            return "call de all-in" + (" (push/fold)" if modo == "push_fold" else f" (modo {modo})")
        return "call grande (no all-in)" if inv >= 0.25 * saldo else "call chico (la pérdida se acumuló en otras calles)"
    if acc in ("bet", "raise"):
        return "bet/raise no all-in, luego pagada"
    return "otra (check/fold)"


def cerca_umbral(desc):
    c = desc["margen_ev"] is not None and desc["margen_ev"] < CERCA_EV
    if desc["accion"] == "call" and desc["e"] is not None and desc["e_min"] is not None:
        c = c or (desc["e"] - desc["e_min"] < CERCA_E)
    return c


# --- Supervivencia -------------------------------------------------------------------------------------------------

def simular(vals, n, rondas, rng):
    vivas = arriba = 0
    for _ in range(n):
        s = 1.0
        for r in rng.choices(vals, k=rondas):
            s *= r
            if s == 0:
                break
        if s > 0:
            vivas += 1
        if s > 1.0:
            arriba += 1
    return vivas / n, arriba / n


def supervivencia(finales, rondas=10, n=100_000, remuestras=300, n_interno=4_000, semilla=7):
    rng = random.Random(semilla)
    ratios = [f / STACK for f in finales]
    p_vivo, p_arriba = simular(ratios, n, rondas, rng)
    vs, ars = [], []
    for _ in range(remuestras):
        rs = rng.choices(ratios, k=len(ratios))
        a, b = simular(rs, n_interno, rondas, rng)
        vs.append(a)
        ars.append(b)
    ic = lambda v: (percentil(v, 2.5), percentil(v, 97.5))
    p0 = sum(1 for r in ratios if r == 0) / len(ratios)
    return {"p_vivo": p_vivo, "p_vivo_ic": ic(vs), "p_vivo_analitico": (1 - p0) ** rondas,
            "p_arriba": p_arriba, "p_arriba_ic": ic(ars), "p_quiebra_mesa": p0,
            "que_pasaria_si": {f"{int(q * 100)} %": round((1 - q) ** rondas, 3) for q in (0.25, 0.15, 0.10, 0.05)}}


# --- Programa principal ----------------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--etiqueta", required=True)
    ap.add_argument("--rondas-torneo", type=int, default=10)
    ap.add_argument("--ejemplos", type=int, default=12, help="manos de quiebra a mostrar en el informe")
    args = ap.parse_args()

    ruta_json = os.path.join(E.SALIDAS, "evaluaciones", f"{args.etiqueta}.json")
    res = json.load(open(ruta_json, encoding="utf-8"))
    detalle = res["mesa"]["detalle"]
    dir_eval = os.path.join(E.SALIDAS, f"eval-{args.etiqueta}")

    validas = [t for t in detalle if t["final"] is not None]
    finales = [t["final"] for t in validas]
    n = len(validas)
    quiebras = sum(1 for f in finales if f == 0)
    lo, hi = wilson(quiebras, n)
    out = {"etiqueta": args.etiqueta, "commit": res.get("commit_completo") or res.get("commit"),
           "referencia": res.get("referencia"), "mesas": n, "descartadas": len(detalle) - n,
           "quiebras": quiebras, "tasa_quiebra": quiebras / n, "tasa_quiebra_ic": (lo, hi),
           "percentiles_stack_final": {p: percentil(finales, p) for p in (5, 25, 50, 75, 95)},
           "media_final": statistics.mean(finales)}

    # --- por rival presente
    por_rival = {}
    for r in res["rivales"]:
        fs = [t["final"] for t in validas if r in t["rivales"]]
        if fs:
            k = sum(1 for f in fs if f == 0)
            por_rival[r] = {"mesas": len(fs), "quiebras": k, "tasa": k / len(fs), "ic": wilson(k, len(fs)),
                            "mediana_final": statistics.median(fs)}
    out["por_rival"] = por_rival

    # --- manos
    grandes, todas_decisivas = [], []
    manos_totales = 0
    quiebra_en_mano = []
    for t in validas:
        ruta = os.path.join(dir_eval, f"mesa-{t['i']}", "bender.jsonl")
        if not os.path.exists(ruta):
            continue
        manos = leer_mesa(ruta, t["i"], t["final"])
        manos_totales += len(manos)
        for k, m in enumerate(manos):
            if m["despues"] == 0 and m["antes"] > 0:
                quiebra_en_mano.append(k + 1)
            ds, invs = inversiones(m)
            perdida = m["antes"] - m["despues"]
            if ds:
                j = max(range(len(ds)), key=lambda q: (invs[q], q))
                desc = describir(m, ds[j], invs[j])
                desc["delta_desde_decision"] = m["despues"] - ds[j]["saldo"]
                desc["gross"] = m["despues"] - ds[j]["saldo"] + invs[j]
                desc["n_decisiones_con_inversion"] = sum(1 for x in invs if x > 0)
            else:
                desc = None
            base = {"mesa": t["i"], "mano": k + 1, "id_mano": m["id"], "stack_antes": m["antes"], "stack_despues": m["despues"],
                    "perdida": perdida, "rivales_en_mano": m["rivales_ids"], "ganadores": m["ganadores"],
                    "quiebra": m["despues"] == 0}
            if desc and desc["inversion"] >= UMBRAL_GRANDE * (desc["saldo"] or 1):
                todas_decisivas.append({**base, **desc})
            if perdida > UMBRAL_GRANDE * m["antes"]:
                fila = {**base, **(desc or {})}
                fila["categoria"] = categoria(desc, bool(desc)) if desc else categoria({}, False)
                fila["cerca_umbral"] = cerca_umbral(desc) if desc else False
                grandes.append(fila)
    out["manos_analizadas"] = manos_totales
    out["manos_grandes"] = len(grandes)
    out["manos_de_quiebra"] = sum(1 for g in grandes if g["quiebra"])
    out["mano_de_la_quiebra"] = {p: percentil(quiebra_en_mano, p) for p in (25, 50, 75)} if quiebra_en_mano else None
    sb = [g["stack_antes"] / BB for g in grandes if g["quiebra"]]
    out["stack_antes_mano_quiebra_bb"] = {p: percentil(sb, p) for p in (25, 50, 75)} if sb else None

    def resumen(filas):
        tab = defaultdict(list)
        for g in filas:
            tab[g["categoria"]].append(g)
        res_t = []
        for cat, gs in sorted(tab.items(), key=lambda x: -len(x[1])):
            es = [g["e"] for g in gs if g.get("e") is not None]
            mg = [g["margen_ev"] for g in gs if g.get("margen_ev") is not None]
            fs = [g["f"] for g in gs if g.get("f") is not None]
            evf = [g["ev_por_fold_pct"] for g in gs if g.get("ev_por_fold_pct") is not None]
            res_t.append({"categoria": cat, "n": len(gs), "pct": len(gs) / len(filas),
                          "f_mediana": statistics.median(fs) if fs else None,
                          "ev_por_fold_mediana": statistics.median(evf) if evf else None,
                          "e_prima_media": statistics.mean([g["e_prima"] for g in gs if g.get("e_prima") is not None] or [float("nan")]),
                          "e_media": statistics.mean(es) if es else None,
                          "pct_e_menor_05": (sum(1 for x in es if x < 0.5) / len(es)) if es else None,
                          "margen_ev_mediano_pct_stack": (statistics.median(mg) * 100) if mg else None,
                          "pct_cerca_umbral": sum(1 for g in gs if g["cerca_umbral"]) / len(gs),
                          "pct_multiway": sum(1 for g in gs if (g.get("n_rivales_decision") or 0) >= 2) / len(gs),
                          "pct_stack_efectivo_menor_30bb": sum(1 for g in gs if (g.get("s_ef_bb") or 999) < 30) / len(gs)})
        return res_t

    out["resumen_manos_grandes"] = resumen(grandes)
    out["resumen_manos_de_quiebra"] = resumen([g for g in grandes if g["quiebra"]])

    def conteo(filas, clave):
        c = Counter(clave(g) for g in filas)
        return dict(c.most_common())
    quiebra_filas = [g for g in grandes if g["quiebra"]]
    for nombre, filas in (("grandes", grandes), ("quiebra", quiebra_filas)):
        out[f"por_calle_{nombre}"] = conteo(filas, lambda g: g.get("etapa"))
        out[f"por_modo_{nombre}"] = conteo(filas, lambda g: g.get("modo"))
        out[f"por_accion_{nombre}"] = conteo(filas, lambda g: g.get("accion"))
        out[f"multiway_{nombre}"] = conteo(filas, lambda g: "multiway (≥2 rivales)" if (g.get("n_rivales_decision") or 0) >= 2 else "heads-up")
        out[f"por_ganador_{nombre}"] = conteo(filas, lambda g: ",".join(x.replace('k-', '') for x in g["ganadores"]) or "?")
        out[f"por_bucket_e_{nombre}"] = conteo(filas, lambda g: "sin e" if g.get("e") is None else
                                                ("e ≥ 0,70" if g["e"] >= 0.7 else "0,50 ≤ e < 0,70" if g["e"] >= 0.5 else "e < 0,50"))
        rec = Counter()
        for g in filas:
            for r in g.get("rivales", []):
                if r["real"] in g["ganadores"] or f"k-{r['real']}" in g["ganadores"]:
                    rec[f"{r['real']} reconocido como {r['bot'] or 'ninguno'} / tipo {r['tipo']}"] += 1
        out[f"rival_ganador_reconocido_{nombre}"] = dict(rec.most_common(15))

    # --- calibración: compromisos grandes (ganados y perdidos)
    cal = defaultdict(list)
    for g in todas_decisivas:
        if g["ev_elegida"] is None:
            continue
        cat = categoria(g, True)
        cal[cat].append(g)
    tabla_cal = []
    for cat, gs in sorted(cal.items(), key=lambda x: -len(x[1])):
        evp = [g["ev_elegida"] / BB for g in gs]
        real = [g["delta_desde_decision"] / BB for g in gs]
        fila = {"categoria": cat, "n": len(gs), "ev_previsto_bb": statistics.mean(evp), "resultado_real_bb": statistics.mean(real),
                "se_real_bb": (statistics.stdev(real) / math.sqrt(len(real))) if len(real) > 1 else None}
        if cat.startswith("call de all-in"):
            es = [g["e"] for g in gs if g["e"] is not None and (g["P"] + g["C"]) > 0]
            real_e = [g["gross"] / (g["P"] + g["C"]) for g in gs if g["e"] is not None and (g["P"] + g["C"]) > 0]
            fila["e_prevista"] = statistics.mean(es) if es else None
            fila["e_realizada"] = statistics.mean(real_e) if real_e else None
        tabla_cal.append(fila)
    out["calibracion_compromisos"] = tabla_cal
    out["compromisos_totales"] = len(todas_decisivas)

    out["supervivencia"] = supervivencia(finales, rondas=args.rondas_torneo)

    # --- salidas a disco
    ruta_out = os.path.join(E.SALIDAS, "evaluaciones", f"quiebras-{args.etiqueta}.json")
    json.dump(out, open(ruta_out, "w", encoding="utf-8"), indent=1, default=str)
    ruta_csv = os.path.join(E.SALIDAS, "evaluaciones", f"quiebras-{args.etiqueta}-manos.csv")
    cols = ["mesa", "mano", "id_mano", "quiebra", "stack_antes", "stack_despues", "perdida", "categoria", "cerca_umbral", "etapa",
            "modo", "accion", "s_ef_bb", "saldo", "inversion", "P", "C", "e", "e_prima", "e_min", "ev_elegida", "margen_ev",
            "n_rivales_decision", "cartas", "comunitarias", "posicion", "ganadores", "rivales_en_mano", "rivales_reconocidos",
            "opciones", "motivo"]
    with open(ruta_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for g in grandes:
            fila = dict(g)
            fila["ganadores"] = ",".join(g["ganadores"])
            fila["rivales_en_mano"] = ",".join(g["rivales_en_mano"])
            fila["rivales_reconocidos"] = "; ".join(f"{r['real']}->{r['bot']}/{r['tipo']}" for r in g.get("rivales", []))
            fila["opciones"] = " | ".join(f"{a}:{ev}{'(desc)' if d else ''}" for a, ev, d in g.get("opciones", []))
            w.writerow(fila)

    imprimir(out, quiebra_filas, args.ejemplos)
    print(f"\n(guardado en {ruta_out} y {ruta_csv})")


def pct(x):
    return "n/d" if x is None else f"{100 * x:.0f} %"


def imprimir(o, quiebra_filas, ejemplos):
    ref = o.get("referencia") or {}
    print(f"## Quiebras de Bender «{o['etiqueta']}»  (commit {str(o['commit'])[:8]}; referencia {ref.get('nombre')} {str(ref.get('commit'))[:8]})")
    lo, hi = o["tasa_quiebra_ic"]
    print(f"\n### 1. Tasa de quiebra y stack final ({o['mesas']} mesas, {o['descartadas']} descartadas)")
    print(f"- Quiebra (0 fichas al final de la mesa): **{o['quiebras']} de {o['mesas']} = {100 * o['tasa_quiebra']:.1f} %** (IC 95 % {100 * lo:.1f}-{100 * hi:.1f} %)")
    p = o["percentiles_stack_final"]
    print("- Stack final (inicial 10 000): " + " | ".join(f"p{k} {v:,.0f}" for k, v in p.items()) + f" | media {o['media_final']:,.0f}")
    if o["mano_de_la_quiebra"]:
        q = o["mano_de_la_quiebra"]
        print(f"- Mano de la mesa en que cae a 0: p25 {q[25]:.0f} | mediana {q[50]:.0f} | p75 {q[75]:.0f} (de 50)")
        s0 = o["stack_antes_mano_quiebra_bb"]
        print(f"- Stack de Bender al EMPEZAR la mano de la quiebra (bb): p25 {s0[25]:.0f} | mediana {s0[50]:.0f} | p75 {s0[75]:.0f} "
              "(si es ~100 bb, la quiebra es una sola mano grande desde stack profundo; si es chico, hubo desgaste antes)")
    print("\n| con este rival en la mesa | mesas | quiebras | tasa | IC 95 % | mediana stack final |\n|---|---|---|---|---|---|")
    for r, v in sorted(o["por_rival"].items(), key=lambda x: -x[1]["tasa"]):
        print(f"| {r} | {v['mesas']} | {v['quiebras']} | {pct(v['tasa'])} | {100 * v['ic'][0]:.0f}-{100 * v['ic'][1]:.0f} % | {v['mediana_final']:,.0f} |")
    print(f"\n### 2-3. Manos en que Bender pierde > 50 % de su stack: {o['manos_grandes']} de {o['manos_analizadas']} manos ({o['manos_de_quiebra']} dejaron a Bender en 0)")
    for titulo, clave in (("Todas las manos grandes", "resumen_manos_grandes"), ("Solo las que lo dejaron en 0", "resumen_manos_de_quiebra")):
        print(f"\n**{titulo}**\n")
        print("| tipo de la decisión decisiva | n | % | e media | e' media | % con e<0,5 | f mediana | % del EV por fold equity | margen EV mediano (% stack) | % cerca del umbral | % multiway | % stack ef.<30 bb |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
        for f in o[clave]:
            e = "n/d" if f["e_media"] is None else f"{f['e_media']:.2f}"
            ep = "n/d" if f["e_prima_media"] != f["e_prima_media"] else f"{f['e_prima_media']:.2f}"
            m = "n/d" if f["margen_ev_mediano_pct_stack"] is None else f"{f['margen_ev_mediano_pct_stack']:.1f}"
            fm = "n/d" if f["f_mediana"] is None else f"{f['f_mediana']:.2f}"
            evf = "n/d" if f["ev_por_fold_mediana"] is None else pct(f["ev_por_fold_mediana"])
            print(f"| {f['categoria']} | {f['n']} | {pct(f['pct'])} | {e} | {ep} | {pct(f['pct_e_menor_05'])} | {fm} | {evf} | {m} | {pct(f['pct_cerca_umbral'])} | {pct(f['pct_multiway'])} | {pct(f['pct_stack_efectivo_menor_30bb'])} |")
    for nombre, etiqueta in (("grandes", "manos grandes"), ("quiebra", "manos de quiebra")):
        print(f"\nCortes ({etiqueta}): calle {o[f'por_calle_{nombre}']} | modo {o[f'por_modo_{nombre}']} | acción {o[f'por_accion_{nombre}']} | {o[f'multiway_{nombre}']} | e {o[f'por_bucket_e_{nombre}']}")
        print(f"  quién ganó el bote: {o[f'por_ganador_{nombre}']}")
    print("\n**Calibración de los compromisos grandes (decisión con inversión ≥ 50 % del stack; ganados y perdidos)** "
          f"({o['compromisos_totales']} decisiones)\n")
    print("| tipo | n | EV previsto (bb) | resultado real (bb) ±EE | e prevista | e realizada |\n|---|---|---|---|---|---|")
    for f in o["calibracion_compromisos"]:
        ee = "" if f["se_real_bb"] is None else f" ±{f['se_real_bb']:.1f}"
        ep = "" if f.get("e_prevista") is None else f"{f['e_prevista']:.3f}"
        er = "" if f.get("e_realizada") is None else f"{f['e_realizada']:.3f}"
        print(f"| {f['categoria']} | {f['n']} | {f['ev_previsto_bb']:+.1f} | {f['resultado_real_bb']:+.1f}{ee} | {ep} | {er} |")
    print(f"\n### Ejemplos de manos de quiebra (primeras {ejemplos}; todas en el CSV)")
    for g in quiebra_filas[:ejemplos]:
        print(f"- mesa {g['mesa']} mano {g['mano']}: {g.get('etapa')} {g.get('modo')} {g.get('accion')} con {g.get('cartas')} sobre [{g.get('comunitarias', '')}] "
              f"stack ef. {g.get('s_ef_bb')} bb, e={g.get('e')}, e'={g.get('e_prima')}, margen EV {g.get('margen_ev')}; ganó {','.join(g['ganadores'])}; "
              f"opciones {[(a, ev) for a, ev, d in g.get('opciones', [])]}")
    s = o["supervivencia"]
    print("\n### 4. Supervivencia de un torneo de 10 rondas (bootstrap de resultados por mesa; APROXIMACIÓN)")
    print(f"- P(terminar las 10 rondas con fichas) = **{100 * s['p_vivo']:.1f} %** (IC 95 % del bootstrap {100 * s['p_vivo_ic'][0]:.1f}-{100 * s['p_vivo_ic'][1]:.1f} %; "
          f"analítico (1−p)^10 = {100 * s['p_vivo_analitico']:.1f} %)")
    print(f"- P(terminar con más de 10 000) = **{100 * s['p_arriba']:.1f} %** (IC 95 % {100 * s['p_arriba_ic'][0]:.1f}-{100 * s['p_arriba_ic'][1]:.1f} %)")
    print(f"- Qué pasaría con otras tasas de quiebra por ronda, P(sobrevivir 10) = {s['que_pasaria_si']}")
    print("- Aproximación: cada ronda multiplica el stack por (fichas finales de una mesa elegida al azar / 10 000); la mesa real arranca "
          "cada ronda con el stack acumulado (no con 10 000) y los rivales cambian; supone rondas independientes.")


if __name__ == "__main__":
    main()
