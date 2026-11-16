#!/usr/bin/env python3
"""Última prueba antes de congelar (pedida por el usuario el 2026-11-16): A = v1.3-limpers, B = k6k, C = k6k + huella corregida.

Los dos campos con semillas NUEVAS (nunca usadas), emparejadas por semilla entre las tres configuraciones:
  - desconocido (28 sin darwin ni novato): 16 000 000 + i
  - entrenamiento (28 sin darwin ni novato): 15 000 000 + i
Se reporta B vs A, C vs A y C vs B (Δ P(top 6), Δ P(sobrevivir), Δ tasa de quiebra por mesa, Δ puesto medio, Δ bb/100; IC 95 %) y los falsos
positivos de la huella.

REGLA (de no inferioridad, del usuario): se elige la configuración más completa (C > B > A) que cumpla
  1. el promedio de los dos campos del estimador de Δ P(top 6) contra A es >= 0;
  2. ningún Δ P(sobrevivir) contra A es significativamente negativo (límite superior del IC < 0) en ningún campo;
  3. (solo C) no es significativamente peor que B en ningún campo: ni en Δ P(top 6) ni en Δ P(sobrevivir) (límite superior del IC < 0).

  bender/.venv/Scripts/python.exe bender/pruebas/evaluar_fijo.py --script final2_eval.py -- --nombre f2
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bandido_eval as BE  # noqa: E402
import campeonato as CAMP  # noqa: E402
import confirmacion as CONF  # noqa: E402
import evaluar as E  # noqa: E402
import final_eval as FE  # noqa: E402
import halving as H  # noqa: E402

SEMILLA_DESC = 16_000_000
SEMILLA_ENT = 15_000_000
IDS = ["base", "k6k", "k6k_huella"]
ETIQ = {"base": "A", "k6k": "B", "k6k_huella": "C"}


def configuraciones():
    c = FE.configuraciones()
    return {"base": c["base"], "k6k": c["k6k"],
            "k6k_huella": {"id": "k6k_huella", "variante": FE.mezclar(c["k6k"]["variante"], FE.FIX["huella"])}}


def signif_negativo(t):
    return t is not None and t[2] < 0


def decidir(res):
    """res = {"B": {"vsA": {campo: {"top6": t, "surv": t}}}, "C": {"vsA": ..., "vsB": ...}}, campo ∈ {"desc","ent"}; t = (est, lo, hi).
    Devuelve ("A"|"B"|"C", líneas explicativas)."""
    why = []
    elegida = "A"
    for x in ("B", "C"):
        r = res.get(x)
        if r is None:
            why.append(f"- {x}: sin datos")
            continue
        prom = sum(r["vsA"][f]["top6"][0] for f in ("desc", "ent")) / 2
        c1 = prom >= 0
        c2 = not any(signif_negativo(r["vsA"][f]["surv"]) for f in ("desc", "ent"))
        c3 = True
        if x == "C":
            c3 = not any(signif_negativo(r["vsB"][f][m]) for f in ("desc", "ent") for m in ("top6", "surv"))
        why.append(f"- {x}: (1) promedio de los dos campos de Δ P(top 6) vs A = {100 * prom:+.1f} pts → {'cumple' if c1 else 'NO cumple'}; "
                   f"(2) ningún Δ P(sobrevivir) significativamente negativo → {'cumple' if c2 else 'NO cumple'}"
                   + (f"; (3) no significativamente peor que B → {'cumple' if c3 else 'NO cumple'}" if x == "C" else ""))
        if c1 and c2 and c3:
            elegida = x                                              # C > B > A: gana la más completa que cumple
    return elegida, why


def ic_top(cor_a, cfg_a, cor_b, cfg_b, sem):
    e = H.emparejar(cor_a.leer(cfg_a, "n", sem), cor_b.leer(cfg_b, "n", sem))
    if not e["n"]:
        return None
    return {"top6": H.ic(e["top6"]), "surv": H.ic(e["sobrevive"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nombre", default="f2")
    ap.add_argument("--paralelo", type=int, default=10)
    ap.add_argument("--n", type=int, default=300, help="campeonatos por configuración y por campo")
    ap.add_argument("--solo-informe", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    C = configuraciones()
    dir_desc = os.path.join(E.SALIDAS, "halving", args.nombre + "-desc")
    dir_ent = os.path.join(E.SALIDAS, "halving", args.nombre + "-ent")
    os.makedirs(dir_desc, exist_ok=True)
    os.makedirs(dir_ent, exist_ok=True)
    json.dump({"commit": os.environ.get("BENDER_COMMIT_COMPLETO"), "campo_desconocido": BE.CAMPO_DESC, "campo_entrenamiento": BE.CAMPO_ENT,
               "configuraciones": C}, open(os.path.join(dir_desc, "configuraciones.json"), "w"), indent=1)
    cor = {"desc": H.Corredor(dir_desc, args.paralelo), "ent": H.Corredor(dir_ent, args.paralelo)}
    cor["desc"].campo = CAMP.campo_de(BE.CAMPO_DESC)
    sem = {"desc": [SEMILLA_DESC + i for i in range(args.n)], "ent": [SEMILLA_ENT + i for i in range(args.n)]}
    t0 = time.time()
    if not args.solo_informe:
        cor["desc"].jugar([C[i] for i in IDS], sem["desc"], "n", f"DESCONOCIDO: {len(IDS)} configuraciones × {args.n} semillas nuevas")
        cor["ent"].jugar([C[i] for i in IDS], sem["ent"], "n", f"ENTRENAMIENTO: {len(IDS)} configuraciones × {args.n} semillas nuevas")

    L = [f"# Prueba final «{args.nombre}» (commit {os.environ.get('BENDER_COMMIT')}; {(time.time() - t0) / 3600:.1f} h en esta corrida)\n",
         "A = v1.3-limpers · B = k6k (solo K = 6000) · C = k6k + huella corregida (P(bot) ≥ 0,97, ≥ 8 apuestas con z, apertura preflop a 3 bb)\n"]
    campos = {"desc": ("DESCONOCIDO", BE.CAMPO_DESC, SEMILLA_DESC), "ent": ("ENTRENAMIENTO", BE.CAMPO_ENT, SEMILLA_ENT)}
    res = {"B": {"vsA": {}}, "C": {"vsA": {}, "vsB": {}}}
    rec = {}
    for f, (nom, campo, s0) in campos.items():
        L.append(f"## Campo {nom} ({campo} + Bender; semillas {s0}+i, {args.n} previstas)\n")
        L.append("Absolutos:\n\n| config | n | P(top 6) | P(sobrevivir) | puesto medio |\n|---|---|---|---|---|")
        for i in IDS:
            BE.absolutos(L, cor[f], C[i], "n", sem[f], f"{ETIQ[i]} ({i})")
        L.append("")
        L += [h.replace("| selector |", "| config |") for h in BE.CABECERA]
        for x, refs in (("k6k", ["base"]), ("k6k_huella", ["base", "k6k"])):
            filas = []
            BE.tabla(filas, f"{ETIQ[x]} ({x})", cor[f], C[x], "n", [(f"{ETIQ[r]} ({r})", cor[f], C[r], "n") for r in refs], sem[f])
            L += [fl.replace("| selector | contra |", "| config | contra |") for fl in filas]
        L.append("")
        res["B"]["vsA"][f] = ic_top(cor[f], C["k6k"], cor[f], C["base"], sem[f])
        res["C"]["vsA"][f] = ic_top(cor[f], C["k6k_huella"], cor[f], C["base"], sem[f])
        res["C"]["vsB"][f] = ic_top(cor[f], C["k6k_huella"], cor[f], C["k6k"], sem[f])
        rec[f] = {i: FE.reconocimiento(cor[f], C[i], "n", sem[f]) for i in IDS}
        FE.tabla_fp(L, f"Reconocimiento de la huella, campo {nom}", rec[f])
        L.append("| config | falsos positivos (rivales que NO son del kit reconocidos como bot del kit) |\n|---|---|")
        for i in IDS:
            L.append(f"| {ETIQ[i]} ({i}) | {FE.fp_total(rec[f][i]):.1f} % de los (mano, rival) |")
        L.append("")

    L.append("## Regla de no inferioridad\n")
    if all(res[x][v].get(f) for x, v in (("B", "vsA"), ("C", "vsA"), ("C", "vsB")) for f in ("desc", "ent")):
        fmt = lambda t: f"{100 * t[0]:+.1f} ({100 * t[1]:+.1f} a {100 * t[2]:+.1f})"
        L.append("| comparación | campo | Δ P(top 6) | Δ P(sobrevivir) |\n|---|---|---|---|")
        for nom, x, v in (("B vs A", "B", "vsA"), ("C vs A", "C", "vsA"), ("C vs B", "C", "vsB")):
            for f in ("desc", "ent"):
                L.append(f"| {nom} | {campos[f][0].lower()} | {fmt(res[x][v][f]['top6'])} | {fmt(res[x][v][f]['surv'])} |")
        veredicto, why = decidir(res)
        L.append("\n" + "\n".join(why))
        L.append(f"\n**Configuración recomendada por la regla: {veredicto} ({'v1.3-limpers' if veredicto == 'A' else 'k6k' if veredicto == 'B' else 'k6k + huella corregida'}).**")
    else:
        L.append("(faltan datos para aplicar la regla)")
    texto = "\n".join(L)
    open(os.path.join(dir_desc, "informe.md"), "w", encoding="utf-8").write(texto)
    print(texto)


if __name__ == "__main__":
    main()
