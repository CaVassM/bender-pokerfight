#!/usr/bin/env python3
"""Capa 3, paso 2: evalúa el bandido ONLINE (UCB con descuento y Exp3) contra los brazos fijos, emparejado por semilla.

Dos campos de 28 participantes (sin darwin ni novato):
  - ENTRENAMIENTO: el del paso 1 (6 bots del kit × 4 + 3 bender_v1). Los brazos FIJOS (base, c05, c24 y k6k) se leen de la corrida
    de confirmación `conf1` (mismas semillas 10 000 000 + i): aquí solo se juegan los dos selectores.
  - DESCONOCIDO: 7 bender_agresivo + 7 bender_prudente + 4 bender_v1 + 2 de cada bot de estrés + 3 aleatorio. Nada de esto es un bot del
    kit reconocible salvo los 3 aleatorios. Se juegan los brazos fijos (base, c05, c24) y los dos selectores, con semillas 11 000 000 + i.

Informe: Δ P(top 6), Δ P(sobrevivir), Δ quiebra por campeonato y por mesa, Δ puesto y Δ bb/100 con IC 95 % del selector contra cada brazo
fijo; y diagnóstico del bandido leído de sus logs (uso de cada brazo, % de manos explorando, recompensa media por brazo).

  bender/.venv/Scripts/python.exe bender/pruebas/evaluar_fijo.py --script bandido_eval.py -- --nombre b1 [--base-id k6k]
"""

import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campeonato as CAMP  # noqa: E402
import confirmacion as CONF  # noqa: E402
import evaluar as E  # noqa: E402
import halving as H  # noqa: E402

CAMPO_ENT = H.CAMPO
CAMPO_DESC = "bender_agresivo:7,bender_prudente:7,bender_v1:4,allin_siempre:2,iguala_siempre:2,sube_min_siempre:2,aleatorio:3"
SEMILLA_ENT = CONF.SEMILLA_NUEVA              # 10_000_000: las mismas que conf1
SEMILLA_DESC = 11_000_000
SELECTORES = ["ucb", "exp3"]


def variantes_bandido():
    return {s: {"id": s, "variante": {"bandido": {"activo": True, "selector": s}}} for s in SELECTORES}


def diagnostico(cor, cfg, bloque, semillas):
    """Lee los logs del bandido: uso de cada brazo, % explorando y recompensa media (z y bb) por brazo."""
    uso, expl, n, rec, recon = {}, 0, 0, {}, {}
    for s in semillas:
        dir_t = os.path.join(cor.dir_cfg(cfg, bloque), f"t{s}")
        ruta = os.path.join(dir_t, "bender.jsonl")
        if not os.path.exists(ruta):
            continue
        try:                                                      # tipo REAL de cada alias, para ver qué reconoce Bender de cada uno
            reales = {p["id"]: p["tipo"] for p in json.load(open(os.path.join(dir_t, "torneo.json"), encoding="utf-8"))["participantes"]}
        except (OSError, ValueError, KeyError):
            reales = {}
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                if '"tipo":"bandido",' in linea:
                    r = json.loads(linea)
                    uso[r["brazo"]] = uso.get(r["brazo"], 0) + 1
                    expl += bool(r["explorar"])
                    n += 1
                    for rv in r["rivales"]:
                        d = recon.setdefault(reales.get(rv["id"], "?"), {})
                        d[rv["tipo"]] = d.get(rv["tipo"], 0) + 1
                elif '"tipo":"bandido_recompensa"' in linea:
                    r = json.loads(linea)
                    rec.setdefault(r["brazo"], []).append((r["z"], (r["S1"] - r["S0"]) / CAMP.BB))
    return n, uso, expl, rec, recon


def tabla(L, etiqueta, cor_sel, cfg_sel, bloque_sel, referencias, sem):
    """Filas del selector contra cada referencia (id, Corredor, bloque)."""
    d_sel = cor_sel.leer(cfg_sel, bloque_sel, sem)
    q_sel = CONF.leer_mesas(cor_sel, cfg_sel, bloque_sel, sem)
    for ref_id, cor_ref, cfg_ref, bloque_ref in referencias:
        d_ref = cor_ref.leer(cfg_ref, bloque_ref, sem)
        e = H.emparejar(d_sel, d_ref)
        if e["n"] == 0:
            continue
        m = {k: H.ic(e[k]) for k in ("top6", "sobrevive", "puesto", "bb100")}
        tq = CONF.ic_tasa(q_sel, CONF.leer_mesas(cor_ref, cfg_ref, bloque_ref, sem))
        L.append(f"| {etiqueta} | {ref_id} | {e['n']} | {100 * m['top6'][0]:+.1f} ({100 * m['top6'][1]:+.1f} a {100 * m['top6'][2]:+.1f}) | "
                 f"{100 * m['sobrevive'][0]:+.1f} ({100 * m['sobrevive'][1]:+.1f} a {100 * m['sobrevive'][2]:+.1f}) | "
                 f"{-100 * m['sobrevive'][0]:+.1f} | {100 * tq[0]:+.2f} ({100 * tq[1]:+.2f} a {100 * tq[2]:+.2f}) | "
                 f"{m['puesto'][0]:+.2f} ({m['puesto'][1]:+.2f} a {m['puesto'][2]:+.2f}) | {m['bb100'][0]:+.0f} ({m['bb100'][1]:+.0f} a {m['bb100'][2]:+.0f}) |")


CABECERA = ["| selector | contra | n | Δ P(top 6) pts (IC 95 %) | Δ P(sobrevivir) pts (IC 95 %) | Δ P(quiebra) por campeonato pts | "
            "Δ tasa de quiebra por mesa pts (IC 95 %) | Δ puesto medio (IC 95 %) | Δ bb/100 (IC 95 %) |", "|---|---|---|---|---|---|---|---|---|"]


def absolutos(L, cor, cfg, bloque, sem, etiqueta):
    d = cor.leer(cfg, bloque, sem)
    if d:
        L.append(f"| {etiqueta} | {len(d)} | {100 * statistics.fmean(v[1] for v in d.values()):.1f} % | {100 * statistics.fmean(v[2] for v in d.values()):.1f} % | "
                 f"{statistics.fmean(v[0] for v in d.values()):.2f} |")


def diag_texto(L, nombre, cor, cfg, bloque, sem):
    n, uso, expl, rec, recon = diagnostico(cor, cfg, bloque, sem)
    if not n:
        return
    L.append(f"- **{nombre}** ({n} manos con elección): uso " + ", ".join(f"{a} {100 * k / n:.1f} %" for a, k in sorted(uso.items())) +
             f"; explorando {100 * expl / n:.1f} % de las manos.")
    filas = []
    for a, v in sorted(rec.items()):
        zs, bbs = [x[0] for x in v], [x[1] for x in v]
        filas.append(f"{a}: z̄ {statistics.fmean(zs):+.3f} (±{statistics.stdev(zs) / len(zs) ** 0.5:.3f}), {statistics.fmean(bbs):+.2f} bb/mano, {len(v)} manos")
    L.append("  - recompensa media por brazo jugado: " + "; ".join(filas))
    # Qué cree Bender que es cada tipo REAL de rival (clave «bot:x» = reconocido como bot del kit por la huella; «tipo:t» = tipo dominante)
    cre = []
    for real, d in sorted(recon.items()):
        tot = sum(d.values())
        top = sorted(d.items(), key=lambda kv: -kv[1])[:3]
        cre.append(f"{real}: " + ", ".join(f"{k} {100 * v / tot:.0f} %" for k, v in top))
    L.append("  - lo que Bender cree de cada rival (por tipo real): " + "; ".join(cre))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nombre", default="b1")
    ap.add_argument("--paralelo", type=int, default=10)
    ap.add_argument("--n-entrenamiento", type=int, default=450)
    ap.add_argument("--n-desconocido", type=int, default=200)
    ap.add_argument("--base-id", default="base", help="brazo 0 fijo de la confirmación (base = v1.3-limpers; k6k si se adoptó v1.4)")
    ap.add_argument("--conf", default="conf1", help="carpeta de la confirmación con los brazos fijos del campo de entrenamiento")
    ap.add_argument("--solo-informe", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    sel = variantes_bandido()
    fijos = CONF.variantes()
    dir_ent = os.path.join(E.SALIDAS, "halving", args.nombre + "-ent")
    dir_desc = os.path.join(E.SALIDAS, "halving", args.nombre + "-desc")
    os.makedirs(dir_ent, exist_ok=True)
    os.makedirs(dir_desc, exist_ok=True)
    json.dump({"commit": os.environ.get("BENDER_COMMIT_COMPLETO"), "campo_entrenamiento": CAMPO_ENT, "campo_desconocido": CAMPO_DESC,
               "selectores": sel, "fijos": fijos}, open(os.path.join(dir_ent, "configuraciones.json"), "w"), indent=1)
    cor_ent = H.Corredor(dir_ent, args.paralelo)
    cor_desc = H.Corredor(dir_desc, args.paralelo)
    cor_desc.campo = CAMP.campo_de(CAMPO_DESC)
    cor_conf = H.Corredor(os.path.join(E.SALIDAS, "halving", args.conf), 1)
    sem_ent = [SEMILLA_ENT + i for i in range(args.n_entrenamiento)]
    sem_desc = [SEMILLA_DESC + i for i in range(args.n_desconocido)]
    t0 = time.time()
    if not args.solo_informe:
        cor_ent.jugar([sel[s] for s in SELECTORES], sem_ent, "n", f"ENTRENAMIENTO: {len(SELECTORES)} selectores × {len(sem_ent)} semillas")
        cor_desc.jugar([fijos["base"], fijos["c05"], fijos["c24"]] + [sel[s] for s in SELECTORES], sem_desc, "n",
                       f"DESCONOCIDO: 3 fijos + {len(SELECTORES)} selectores × {len(sem_desc)} semillas")

    L = [f"# Paso 2: bandido online «{args.nombre}» (commit {os.environ.get('BENDER_COMMIT')}; {(time.time() - t0) / 3600:.1f} h en esta corrida)\n"]
    # ---- entrenamiento ----
    L.append(f"## Campo de ENTRENAMIENTO ({CAMPO_ENT} + Bender; semillas {SEMILLA_ENT}+i; brazos fijos de «{args.conf}»)\n")
    L.append("Absolutos:\n\n| config | n | P(top 6) | P(sobrevivir) | puesto medio |\n|---|---|---|---|---|")
    for fid in (args.base_id, "c05", "c24") + (("k6k",) if args.base_id != "k6k" else ()):
        absolutos(L, cor_conf, fijos[fid], "n", sem_ent, f"{fid} (fijo)")
    for s in SELECTORES:
        absolutos(L, cor_ent, sel[s], "n", sem_ent, f"{s} (bandido)")
    L.append("")
    L += CABECERA
    refs = [(f"{fid} (fijo)", cor_conf, fijos[fid], "n") for fid in (args.base_id, "c05", "c24")]
    for s in SELECTORES:
        tabla(L, s, cor_ent, sel[s], "n", refs, sem_ent)
    L.append("\n### Diagnóstico del bandido (entrenamiento)\n")
    for s in SELECTORES:
        diag_texto(L, s, cor_ent, sel[s], "n", sem_ent)
    # ---- desconocido ----
    L.append(f"\n## Campo DESCONOCIDO ({CAMPO_DESC} + Bender; semillas {SEMILLA_DESC}+i)\n")
    L.append("Absolutos:\n\n| config | n | P(top 6) | P(sobrevivir) | puesto medio |\n|---|---|---|---|---|")
    for fid in ("base", "c05", "c24"):
        absolutos(L, cor_desc, fijos[fid], "n", sem_desc, f"{fid} (fijo)")
    for s in SELECTORES:
        absolutos(L, cor_desc, sel[s], "n", sem_desc, f"{s} (bandido)")
    L.append("")
    L += CABECERA
    refs = [(f"{fid} (fijo)", cor_desc, fijos[fid], "n") for fid in ("base", "c05", "c24")]
    for s in SELECTORES:
        tabla(L, s, cor_desc, sel[s], "n", refs, sem_desc)
    for fid in ("c05", "c24"):                                  # ¿alguno de los brazos fijos le gana a la base en este campo?
        tabla(L, fid + " (fijo)", cor_desc, fijos[fid], "n", [("base (fijo)", cor_desc, fijos["base"], "n")], sem_desc)
    L.append("\n### Diagnóstico del bandido (desconocido)\n")
    for s in SELECTORES:
        diag_texto(L, s, cor_desc, sel[s], "n", sem_desc)
    texto = "\n".join(L)
    open(os.path.join(dir_ent, "informe.md"), "w", encoding="utf-8").write(texto)
    print(texto)


if __name__ == "__main__":
    main()
