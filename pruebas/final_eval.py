#!/usr/bin/env python3
"""Capa 3, última ronda antes de congelar: base, c05, k6k y las dos correcciones de la huella, en el campo «desconocido».

Configuraciones (todas contra v1.3-limpers = «base», emparejado por semilla):
  base        v1.3-limpers
  c05         finalista del halving h1 (con su s_prior)
  k6k         v1.3-limpers con solo K = 6000
  sin_contra  base con `explotacion.contra_bots` apagado (ninguna plantilla de bot del kit)
  huella      base con la huella corregida: P(bot) >= 0,97, al menos 8 apuestas con z medido (`huella.min_z`) y el tamaño de la apertura
              preflop como evidencia (`huella.apertura_3bb`: los bots del kit base, bandido y espia abren a 3 bb exactos)
  c05_<fix>   (opcional, `--fix sin_contra|huella`) c05 + la corrección elegida

Campo DESCONOCIDO (28 sin darwin ni novato): 7 bender_agresivo + 7 bender_prudente + 4 bender_v1 + 2 de cada bot de estrés + 3 aleatorio.
200 semillas NUEVAS (14 000 000 + i). Campo de ENTRENAMIENTO: las correcciones (y c05_<fix>) con las primeras 200 semillas de «conf1»
(10 000 000 + i), emparejadas con la base de conf1, para ver que no pierden donde los bots del kit SÍ están en la mesa.

Además de la tabla: tasa de FALSOS POSITIVOS de la huella = % de (mano, rival) en que un rival que NO es del kit (copias de Bender, bots de
estrés) queda reconocido como bot del kit con P >= umbral en alguna decisión de esa mano (se lee de `info.rivales[*].bot` del log de Bender).

  bender/.venv/Scripts/python.exe bender/pruebas/evaluar_fijo.py --script final_eval.py -- --nombre f1
"""

import argparse
import copy
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bandido_eval as BE  # noqa: E402
import campeonato as CAMP  # noqa: E402
import confirmacion as CONF  # noqa: E402
import evaluar as E  # noqa: E402
import halving as H  # noqa: E402

SEMILLA_DESC = 14_000_000
KIT = {"aleatorio", "conservador", "base", "estadistico", "bandido", "espia"}       # tipos reales que SÍ son bots del kit (en estos campos: aleatorio)
FIX = {"sin_contra": {"explotacion": {"contra_bots": False}},
       "huella": {"huella": {"umbral": 0.97, "min_z": 8, "apertura_3bb": {"activa": True}}}}
ORDEN_SENCILLEZ = ["base", "k6k", "sin_contra", "huella", "c05", "c05_sin_contra", "c05_huella"]


def mezclar(a, b):
    out = copy.deepcopy(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = mezclar(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def configuraciones():
    fijos = CONF.variantes()
    cfgs = {"base": fijos["base"], "c05": fijos["c05"], "k6k": fijos["k6k"]}
    for nombre, v in FIX.items():
        cfgs[nombre] = {"id": nombre, "variante": copy.deepcopy(v)}
        cfgs["c05_" + nombre] = {"id": "c05_" + nombre, "variante": mezclar(fijos["c05"]["variante"], v)}
    return cfgs


def reconocimiento(cor, cfg, bloque, semillas):
    """{tipo real: {"pares": n, "reconocidos": {nombre del bot: n}}} por (mano, rival); un par cuenta como reconocido si en alguna
    decisión de esa mano `bot_reconocido()` devolvió un bot."""
    out = {}
    for s in semillas:
        dir_t = os.path.join(cor.dir_cfg(cfg, bloque), f"t{s}")
        ruta = os.path.join(dir_t, "bender.jsonl")
        if not os.path.exists(ruta):
            continue
        try:
            reales = {p["id"]: p["tipo"] for p in json.load(open(os.path.join(dir_t, "torneo.json"), encoding="utf-8"))["participantes"]}
        except (OSError, ValueError, KeyError):
            continue
        vistos = {}
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                if '"tipo":"decision"' not in linea or '"bot":' not in linea:
                    continue
                r = json.loads(linea)
                for i, v in (r.get("info", {}).get("rivales") or {}).items():
                    clave = (r["id_mano"], i)
                    bot = (v.get("bot") or [None])[0]
                    if clave not in vistos or (bot and not vistos[clave]):
                        vistos[clave] = bot
        for (_, i), bot in vistos.items():
            d = out.setdefault(reales.get(i, "?"), {"pares": 0, "reconocidos": {}})
            d["pares"] += 1
            if bot:
                d["reconocidos"][bot] = d["reconocidos"].get(bot, 0) + 1
    return out


def tabla_fp(L, titulo, por_config):
    """Una fila por (config, tipo real): % de pares reconocidos como bot del kit."""
    L.append(f"**{titulo}**\n")
    L.append("| config | tipo real | (mano, rival) | reconocido como bot del kit | desglose | clase |\n|---|---|---|---|---|---|")
    for cid, rec in por_config.items():
        for tipo, d in sorted(rec.items()):
            n, k = d["pares"], sum(d["reconocidos"].values())
            if not n:
                continue
            top = ", ".join(f"{b} {100 * v / n:.0f} %" for b, v in sorted(d["reconocidos"].items(), key=lambda kv: -kv[1])[:3])
            if tipo in KIT:
                bien = d["reconocidos"].get(tipo, 0)
                clase = f"kit: bien reconocido {100 * bien / n:.0f} %"
            else:
                clase = "NO kit: falso positivo"
            L.append(f"| {cid} | {tipo} | {n} | {100 * k / n:.1f} % | {top or '—'} | {clase} |")
    L.append("")


def fp_total(rec):
    """% de pares (mano, rival) de rivales NO kit reconocidos como bot del kit, agregado."""
    n = sum(d["pares"] for t, d in rec.items() if t not in KIT)
    k = sum(sum(d["reconocidos"].values()) for t, d in rec.items() if t not in KIT)
    return 100.0 * k / n if n else float("nan")


def veredicto(punto, lo, hi):
    return "gana" if lo > 0 else ("pierde" if hi < 0 else "empata")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nombre", default="f1")
    ap.add_argument("--paralelo", type=int, default=10)
    ap.add_argument("--n-desconocido", type=int, default=200)
    ap.add_argument("--n-entrenamiento", type=int, default=200)
    ap.add_argument("--configs-desc", default="base,c05,k6k,sin_contra,huella")
    ap.add_argument("--configs-ent", default="sin_contra,huella")
    ap.add_argument("--fase", default="todo", choices=["desconocido", "entrenamiento", "todo"])
    ap.add_argument("--solo-informe", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    C = configuraciones()
    ids_desc, ids_ent = args.configs_desc.split(","), [c for c in args.configs_ent.split(",") if c]
    dir_desc = os.path.join(E.SALIDAS, "halving", args.nombre + "-desc")
    dir_ent = os.path.join(E.SALIDAS, "halving", args.nombre + "-ent")
    os.makedirs(dir_desc, exist_ok=True)
    os.makedirs(dir_ent, exist_ok=True)
    json.dump({"commit": os.environ.get("BENDER_COMMIT_COMPLETO"), "campo_desconocido": BE.CAMPO_DESC, "campo_entrenamiento": BE.CAMPO_ENT,
               "configuraciones": C}, open(os.path.join(dir_desc, "configuraciones.json"), "w"), indent=1)
    cor_desc, cor_ent = H.Corredor(dir_desc, args.paralelo), H.Corredor(dir_ent, args.paralelo)
    cor_desc.campo = CAMP.campo_de(BE.CAMPO_DESC)
    cor_conf = H.Corredor(os.path.join(E.SALIDAS, "halving", "conf1"), 1)
    sem_desc = [SEMILLA_DESC + i for i in range(args.n_desconocido)]
    sem_ent = [CONF.SEMILLA_NUEVA + i for i in range(args.n_entrenamiento)]
    t0 = time.time()
    if not args.solo_informe:
        if args.fase in ("desconocido", "todo"):
            cor_desc.jugar([C[i] for i in ids_desc], sem_desc, "n", f"DESCONOCIDO: {len(ids_desc)} configuraciones × {len(sem_desc)} semillas nuevas")
        if args.fase in ("entrenamiento", "todo") and ids_ent:
            cor_ent.jugar([C[i] for i in ids_ent], sem_ent, "n", f"ENTRENAMIENTO: {len(ids_ent)} configuraciones × {len(sem_ent)} semillas (base de conf1)")

    L = [f"# Última ronda «{args.nombre}» (commit {os.environ.get('BENDER_COMMIT')}; {(time.time() - t0) / 3600:.1f} h en esta corrida)\n"]
    L.append(f"## Campo DESCONOCIDO ({BE.CAMPO_DESC} + Bender; semillas {SEMILLA_DESC}+i; {args.n_desconocido} previstas)\n")
    L.append("Absolutos:\n\n| config | n | P(top 6) | P(sobrevivir) | puesto medio |\n|---|---|---|---|---|")
    for i in ids_desc:
        BE.absolutos(L, cor_desc, C[i], "n", sem_desc, i)
    L.append("")
    L += [h.replace("| selector |", "| config |") for h in BE.CABECERA]
    resumen = {}
    for i in ids_desc:
        if i == "base":
            continue
        filas = []
        BE.tabla(filas, i, cor_desc, C[i], "n", [("base", cor_desc, C["base"], "n")], sem_desc)
        L += [f.replace("| selector | contra |", "| config | contra |") for f in filas]
        e = H.emparejar(cor_desc.leer(C[i], "n", sem_desc), cor_desc.leer(C["base"], "n", sem_desc))
        if e["n"]:
            m, lo, hi = H.ic(e["top6"])
            resumen[i] = {"desc": (m, lo, hi, veredicto(m, lo, hi))}
    if "c05" in ids_desc and "k6k" in ids_desc:
        L.append("")
        filas = []
        BE.tabla(filas, "c05", cor_desc, C["c05"], "n", [("k6k", cor_desc, C["k6k"], "n")], sem_desc)
        L += filas
    L.append("")
    rec_desc = {i: reconocimiento(cor_desc, C[i], "n", sem_desc) for i in ids_desc}
    tabla_fp(L, "Reconocimiento de la huella en el campo desconocido", rec_desc)
    L.append("| config | falsos positivos (rivales que NO son del kit reconocidos como bot del kit) |\n|---|---|")
    for i in ids_desc:
        L.append(f"| {i} | {fp_total(rec_desc[i]):.1f} % de los (mano, rival) |")

    # ---- entrenamiento ----
    if ids_ent:
        L.append(f"\n## Campo de ENTRENAMIENTO ({BE.CAMPO_ENT} + Bender; semillas {CONF.SEMILLA_NUEVA}+i, primeras {args.n_entrenamiento}; base y brazos de «conf1»)\n")
        L.append("Absolutos:\n\n| config | n | P(top 6) | P(sobrevivir) | puesto medio |\n|---|---|---|---|---|")
        BE.absolutos(L, cor_conf, C["base"], "n", sem_ent, "base (conf1)")
        for i in ("c05", "k6k"):
            BE.absolutos(L, cor_conf, C[i], "n", sem_ent, f"{i} (conf1)")
        for i in ids_ent:
            BE.absolutos(L, cor_ent, C[i], "n", sem_ent, i)
        L.append("")
        L += [h.replace("| selector |", "| config |") for h in BE.CABECERA]
        for i in ids_ent:
            filas = []
            BE.tabla(filas, i, cor_ent, C[i], "n", [("base (conf1)", cor_conf, C["base"], "n")], sem_ent)
            L += [f.replace("| selector | contra |", "| config | contra |") for f in filas]
            e = H.emparejar(cor_ent.leer(C[i], "n", sem_ent), cor_conf.leer(C["base"], "n", sem_ent))
            if e["n"]:
                m, lo, hi = H.ic(e["top6"])
                resumen.setdefault(i, {})["ent"] = (m, lo, hi, veredicto(m, lo, hi))
        for i in ("c05", "k6k"):                                  # estos ya tienen todas sus semillas en conf1: acumulado de la confirmación
            e = H.emparejar(cor_conf.leer(C[i], "n", sem_ent), cor_conf.leer(C["base"], "n", sem_ent))
            if e["n"]:
                m, lo, hi = H.ic(e["top6"])
                resumen.setdefault(i, {})["ent"] = (m, lo, hi, veredicto(m, lo, hi))
        L.append("")
        rec_ent = {i: reconocimiento(cor_ent, C[i], "n", sem_ent) for i in ids_ent}
        tabla_fp(L, "Reconocimiento de la huella en el campo de entrenamiento (aquí los bots del kit SÍ están en la mesa)", rec_ent)

    # ---- regla de elección ----
    L.append("\n## Regla de elección (más simple que (i) no pierde en entrenamiento y (ii) gana o empata en el desconocido)\n")
    L.append("| config | (i) entrenamiento: Δ P(top 6) | (ii) desconocido: Δ P(top 6) |\n|---|---|---|")
    for i in ORDEN_SENCILLEZ:
        r = resumen.get(i)
        if not r:
            continue
        f = lambda t: "—" if t is None else f"{100 * t[0]:+.1f} ({100 * t[1]:+.1f} a {100 * t[2]:+.1f}) → {t[3]}"
        L.append(f"| {i} | {f(r.get('ent'))} | {f(r.get('desc'))} |")
    texto = "\n".join(L)
    open(os.path.join(dir_desc, "informe.md"), "w", encoding="utf-8").write(texto)
    print(texto)


if __name__ == "__main__":
    main()
