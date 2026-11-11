#!/usr/bin/env python3
"""Calibración con los bots del kit (paso 4): huella de montos (§2.7), m (§2.5) y prior de tipos (§2.3).

Lee la memoria que Bender dejó de cada rival en las mesas de una evaluación
(salidas/eval-<etiqueta>/mesa-*/rivales/k-<bot>.json), suma los contadores crudos de todas las mesas
y calcula:

  1. Huella: P(caja de z | bot) con las cajas de §2.7, con suavizado de Laplace (+0,5 por caja) y piso 0,01.
  2. m: promedio de la población de bots del kit para VPIP, PFR, "sigue ante apuesta chica" y "sigue
     ante apuesta grande" (cada bot pesa lo mismo).
  3. Prior de tipos: cada bot se clasifica con reglas simples sobre sus estadísticas, y el prior es la
     proporción de bots en cada tipo (con +0,5 de suavizado para que ningún tipo quede en cero).

Solo usa los rivales de ENTRENAMIENTO (aleatorio, conservador, base, estadistico, bandido, espia).
darwin y novato son de reserva: no entran en ninguna calibración.

Uso: bender/.venv/Scripts/python.exe bender/pruebas/calibrar.py <etiqueta> [<etiqueta> ...]
Escribe bender/datos/calibracion.json y lo imprime.
"""

import glob
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SALIDAS = os.path.join(RAIZ, "bender", "pruebas", "salidas")
sys.path.insert(0, os.path.join(RAIZ, "bender"))
from params import PARAMS  # noqa: E402

ENTRENAMIENTO = ["aleatorio", "conservador", "base", "estadistico", "bandido", "espia"]
CAJAS = PARAMS["huella"]["cajas"] + ["otro"]
TIPOS = PARAMS["tipos"]


def leer(etiquetas):
    """{bot: contadores sumados}."""
    acc = {}
    for et in etiquetas:
        for ruta in glob.glob(os.path.join(SALIDAS, f"eval-{et}", "mesa-*", "rivales", "k-*.json")):
            bot = os.path.basename(ruta)[2:-5]
            if bot not in ENTRENAMIENTO:
                continue
            with open(ruta, encoding="utf-8") as f:
                d = json.load(f)
            a = acc.setdefault(bot, {"mesas": 0, "manos": 0, "showdowns": 0, "cajas_z": [0] * len(CAJAS),
                                     "fcr": {"F": 0, "C": 0, "R": 0}, "post": {}, "stats": {}})
            a["mesas"] += 1
            c = d["contadores"]
            a["manos"] += c["manos"]
            a["showdowns"] += c["showdowns"]
            a["cajas_z"] = [x + y for x, y in zip(a["cajas_z"], c["cajas_z"])]
            for k, v in c["preflop_fcr"].items():
                a["fcr"][k] += v
            for k, v in c["post"].items():
                a["post"][k] = a["post"].get(k, 0) + v
            for n, s in d["stats"].items():
                k0, n0 = a["stats"].get(n, (0, 0))
                a["stats"][n] = (k0 + s["k"], n0 + s["n"])
    return acc


def frac(par):
    k, n = par
    return k / n if n else float("nan")


def metricas(a):
    p = a["post"]
    agresion = (p.get("apuestas", 0) + p.get("subidas", 0)) / max(1, p.get("pagos", 0))
    fold_ante_apuesta = p.get("retiros_ante_apuesta", 0) / max(1, p.get("enfrentadas", 0))
    fcr = a["fcr"]
    tot = max(1, sum(fcr.values()))
    return {"vpip": frac(a["stats"]["vpip"]), "pfr": frac(a["stats"]["pfr"]), "sigue_chica": frac(a["stats"]["sigue_chica"]),
            "sigue_grande": frac(a["stats"]["sigue_grande"]), "agresion_post": agresion, "fold_ante_apuesta": fold_ante_apuesta,
            "pre_F": fcr["F"] / tot, "pre_C": fcr["C"] / tot, "pre_R": fcr["R"] / tot,
            "n_z": sum(a["cajas_z"]), "n_sigue_chica": a["stats"]["sigue_chica"][1], "n_sigue_grande": a["stats"]["sigue_grande"][1]}


def clasificar(m, frac_otro):
    """Regla simple (documentada): tipo de un bot a partir de sus estadísticas medidas.

      aleatorio  sus montos postflop caen casi siempre en "otro" (tamaños al azar): >= 60 %
      station    juega casi todo y casi nunca sube: VPIP >= 0,60 y PFR <= 0,05
      maníaco    sube mucho y apuesta mucho más de lo que paga: PFR >= 0,30 y agresión >= 2
      nit        entra con poco: VPIP < 0,20
      TAG        el resto (entra con un rango moderado y apuesta con manos hechas)
    (La agresión postflop apuestas/pagos NO decide sola: un bot que nunca paga, como base, la tiene altísima.)"""
    if frac_otro >= 0.60:
        return "aleatorio"
    if m["vpip"] >= 0.60 and m["pfr"] <= 0.05:
        return "station"
    if m["pfr"] >= 0.30 and m["agresion_post"] >= 2.0:
        return "maniaco"
    if m["vpip"] < 0.20:
        return "nit"
    return "tag"


def main():
    etiquetas = sys.argv[1:]
    if not etiquetas:
        sys.exit(__doc__)
    acc = leer(etiquetas)
    if not acc:
        sys.exit("no se encontró memoria de rivales (¿se corrió evaluar.py --solo-mesa con la Capa 2 activa?)")

    mets = {b: metricas(a) for b, a in acc.items()}
    print("## Estadísticas medidas de cada bot del kit (suma de todas las mesas)\n")
    print("| bot | mesas | manos | VPIP | PFR | pre F/C/R | agresión post | retira ante apuesta | sigue chica | sigue grande | n(z) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for b in ENTRENAMIENTO:
        if b in mets:
            m, a = mets[b], acc[b]
            print(f"| {b} | {a['mesas']} | {a['manos']} | {m['vpip']:.2f} | {m['pfr']:.2f} | {m['pre_F']:.2f}/{m['pre_C']:.2f}/{m['pre_R']:.2f} | "
                  f"{m['agresion_post']:.2f} | {m['fold_ante_apuesta']:.2f} | {m['sigue_chica']:.2f} | {m['sigue_grande']:.2f} | {m['n_z']} |")

    # 1) Huella
    tabla = {}
    for b in ENTRENAMIENTO:
        if b not in acc or sum(acc[b]["cajas_z"]) < 30:
            continue
        cz = acc[b]["cajas_z"]
        n = sum(cz)
        p = [(c + 0.5) / (n + 0.5 * len(cz)) for c in cz]
        p = [max(x, 0.01) for x in p]
        s = sum(p)
        tabla[b] = [round(x / s, 3) for x in p]
    print("\n## Huella P(caja de z | bot), cajas " + " ".join(str(c) for c in CAJAS))
    for b, fila in tabla.items():
        print(f"{b:12} n={sum(acc[b]['cajas_z']):5} " + " ".join(f"{x:.3f}" for x in fila))
    sin_datos = [b for b in ENTRENAMIENTO if b in acc and b not in tabla]
    if sin_datos:
        print(f"(sin suficientes apuestas postflop para la huella: {sin_datos})")

    # 2) m
    nombres = ["vpip", "pfr", "sigue_chica", "sigue_grande"]
    m_pob = {}
    for n in nombres:
        vals = [mets[b][n] for b in mets if mets[b][n] == mets[b][n]]
        m_pob[n] = round(sum(vals) / len(vals), 3)
    print("\n## m: promedio de la población de bots del kit (cada bot pesa igual)")
    print(m_pob)

    # 3) prior de tipos
    clases = {b: clasificar(mets[b], (acc[b]["cajas_z"][-1] / sum(acc[b]["cajas_z"])) if sum(acc[b]["cajas_z"]) >= 30 else 0.0)
              for b in mets}
    cuentas = {t: 0.5 for t in TIPOS}
    for t in clases.values():
        cuentas[t] += 1
    z = sum(cuentas.values())
    prior = {t: round(v / z, 3) for t, v in cuentas.items()}
    print("\n## Tipo de cada bot (reglas en clasificar(): aleatorio si >=60 % de sus montos caen en 'otro'; station si "
          "VPIP>=0,60 y PFR<=0,05; maníaco si PFR>=0,30 y agresión>=2; nit si VPIP<0,20; TAG el resto)")
    print(clases)
    print("prior de tipos (proporción + 0,5 de suavizado):", prior)

    # 4) P(F/C/R | tipo) preflop (§2.3): conteos agregados de los bots de cada tipo (+1 de suavizado)
    fcr = {}
    for tipo in TIPOS:
        bots = [b for b, t in clases.items() if t == tipo]
        if not bots:
            continue
        tot = {k: sum(acc[b]["fcr"][k] for b in bots) + 1 for k in "FCR"}
        z = sum(tot.values())
        fcr[tipo] = {k: round(v / z, 3) for k, v in tot.items()}
    print("\n## P(F/C/R | tipo) preflop medido (bots de cada tipo; los tipos sin bot en el kit conservan la tabla del .tex)")
    for tipo, fila in fcr.items():
        print(f"{tipo:10} {[b for b, t in clases.items() if t == tipo]}  F={fila['F']:.3f} C={fila['C']:.3f} R={fila['R']:.3f}")

    salida = {"etiquetas": etiquetas, "metricas": mets, "huella_tabla": tabla, "huella_cajas": CAJAS, "m": m_pob,
              "tipos": clases, "prior_tipos": prior, "preflop_fcr": fcr}
    ruta = os.path.join(RAIZ, "bender", "datos", "calibracion.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(salida, f, indent=1)
    print(f"\n(guardado en {ruta})")


if __name__ == "__main__":
    main()
