#!/usr/bin/env python3
"""Mide el tamaño de la PRIMERA subida preflop de la mano (la apertura) de cada tipo real de jugador, con los mensajes crudos de campeonatos
ya jugados con BENDER_MENSAJES=1 (los de `medir_sidepots.py`). Resultado que calibra `huella.apertura_3bb.p3` en params.py:
base, bandido y espia abren SIEMPRE a 3 bb exactos; estadistico a 2,0-2,7 bb; aleatorio a tamaños al azar; Bender a 2,5 bb.

  bender/.venv/Scripts/python.exe bender/pruebas/medir_apertura_bots.py [--dir pruebas/salidas/sidepots/runs/m-base]
"""
import json, os, sys, collections
import argparse
ap = argparse.ArgumentParser()
ap.add_argument("--dir", default="pruebas/salidas/sidepots/runs/m-base")
base = ap.parse_args().dir
cnt = collections.defaultdict(collections.Counter)
tot = collections.Counter()
for d in sorted(os.listdir(base)):
    dd = os.path.join(base, d)
    try:
        reales = {p["id"]: p["tipo"] for p in json.load(open(os.path.join(dd, "torneo.json")))["participantes"]}
    except Exception:
        continue
    vistos = set(); abierta = set()
    for linea in open(os.path.join(dd, "bender.jsonl"), encoding="utf-8"):
        if '"tipo":"msg"' not in linea:
            continue
        m = json.loads(linea)["msg"]
        est = m.get("estado") or {}
        h = est.get("historial_acciones") or []
        idm = est.get("id_mano")
        for i, a in enumerate(h):
            if (idm, i) in vistos:
                continue
            vistos.add((idm, i))
            if a.get("etapa") != "preflop":
                continue
            ac = a.get("accion") or {}
            if ac.get("tipo") in ("raise", "bet") and idm not in abierta:
                abierta.add(idm)
                t = reales.get(a["id_jugador"], "?")
                bb = round((ac.get("monto") or 0) / 100.0, 2)
                cnt[t][bb] += 1; tot[t] += 1
for t in sorted(cnt):
    top = cnt[t].most_common(6)
    print(t, tot[t], "exactamente 3 bb: %.0f%%" % (100*cnt[t][3.0]/tot[t]), top)
