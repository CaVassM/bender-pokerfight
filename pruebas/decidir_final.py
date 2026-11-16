#!/usr/bin/env python3
"""Regla de elección de la versión final (decidida por el usuario el 2026-11-16), aplicada a los resultados de `final_eval.py`.

Todo es Δ P(top 6) emparejado contra v1.3-limpers, con IC 95 %.
  - «NO PIERDE»: estimador puntual >= −2 pts Y límite inferior del IC >= −8 pts.
  - ARREGLOS DE ROBUSTEZ (huella, sin_contra): se adoptan si NO PIERDEN en entrenamiento Y en desconocido y, para `huella`, además baja la
    tasa de falsos positivos de la huella (en `sin_contra` la huella no cambia: solo se deja de usar, así que esa condición no aplica).
    Si pasan los dos, huella (conserva el reconocimiento real de los bots del kit).
  - CAMBIOS DE PARÁMETROS (c05, k6k): se adoptan solo si GANAN en el desconocido (IC 95 % que excluye el 0 a favor) y NO PIERDEN en
    entrenamiento. Si pasan los dos, k6k (más simple).
  - Si pasan un arreglo y un parámetro: se lanza la combinación f (≈ 1,2 h) y se adopta si no pierde contra cada uno por separado.
  - Si no pasa nada: la final es v1.3-limpers.

  bender/.venv/Scripts/python.exe bender/pruebas/evaluar_fijo.py --script decidir_final.py -- --nombre f1
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MARGEN_PUNTUAL, MARGEN_LIMITE = -0.02, -0.08


def no_pierde(t):
    """t = (estimador, límite inferior, límite superior) de Δ P(top 6) en fracción (no en puntos)."""
    return t is not None and t[0] >= MARGEN_PUNTUAL and t[1] >= MARGEN_LIMITE


def gana(t):
    return t is not None and t[1] > 0


def decidir(res):
    """res = {config: {"ent": t|None, "desc": t|None, "fp": % de falsos positivos}}; debe traer "base" con su "fp".
    Devuelve (veredicto, líneas explicativas). veredicto: "base" | "huella" | "sin_contra" | "k6k" | "c05" | ("f", arreglo, parámetro)."""
    why = []
    ok_arreglos = []
    for c in ("huella", "sin_contra"):
        r = res.get(c)
        if r is None:
            why.append(f"- {c}: sin datos")
            continue
        e, d = no_pierde(r.get("ent")), no_pierde(r.get("desc"))
        fp = r["fp"] < res["base"]["fp"] if c == "huella" else True
        why.append(f"- {c} (arreglo): no pierde en entrenamiento {'sí' if e else 'NO'}; en desconocido {'sí' if d else 'NO'}; "
                   + (f"falsos positivos {res['base']['fp']:.1f} % → {r['fp']:.1f} % ({'bajan' if fp else 'NO bajan'})" if c == "huella"
                      else "falsos positivos: no aplica (la huella no cambia)"))
        if e and d and fp:
            ok_arreglos.append(c)
    ok_params = []
    for c in ("k6k", "c05"):
        r = res.get(c)
        if r is None:
            why.append(f"- {c}: sin datos")
            continue
        g, e = gana(r.get("desc")), no_pierde(r.get("ent"))
        why.append(f"- {c} (parámetros): gana en desconocido {'sí' if g else 'NO'}; no pierde en entrenamiento {'sí' if e else 'NO'}")
        if g and e:
            ok_params.append(c)
    arreglo = "huella" if "huella" in ok_arreglos else (ok_arreglos[0] if ok_arreglos else None)
    parametro = "k6k" if "k6k" in ok_params else (ok_params[0] if ok_params else None)
    if arreglo and parametro:
        return ("f", arreglo, parametro), why
    return (arreglo or parametro or "base"), why


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nombre", default="f1")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    import campeonato as CAMP
    import bandido_eval as BE
    import confirmacion as CONF
    import evaluar as E
    import final_eval as FE
    import halving as H

    C = FE.configuraciones()
    d_desc = os.path.join(E.SALIDAS, "halving", args.nombre + "-desc")
    d_ent = os.path.join(E.SALIDAS, "halving", args.nombre + "-ent")
    cor_desc, cor_ent = H.Corredor(d_desc, 1), H.Corredor(d_ent, 1)
    cor_desc.campo = CAMP.campo_de(BE.CAMPO_DESC)
    cor_conf = H.Corredor(os.path.join(E.SALIDAS, "halving", "conf1"), 1)
    cor_h1 = H.Corredor(os.path.join(E.SALIDAS, "halving", "h1"), 1)
    sem_desc = [FE.SEMILLA_DESC + i for i in range(200)]
    sem_200 = [CONF.SEMILLA_NUEVA + i for i in range(200)]
    sem_n = [CONF.SEMILLA_NUEVA + i for i in range(CONF.N_NUEVAS)]
    sem_h1 = [CONF.SEMILLA_VALID_H1 + i for i in range(CONF.N_VALID_H1)]

    def delta(a, b):
        e = H.emparejar(a, b)
        return H.ic(e["top6"]) if e["n"] else None

    res = {"base": {"fp": FE.fp_total(FE.reconocimiento(cor_desc, C["base"], "n", sem_desc))}}
    base_desc = cor_desc.leer(C["base"], "n", sem_desc)
    for c in ("huella", "sin_contra", "k6k", "c05"):
        res[c] = {"desc": delta(cor_desc.leer(C[c], "n", sem_desc), base_desc),
                  "fp": FE.fp_total(FE.reconocimiento(cor_desc, C[c], "n", sem_desc))}
    base_conf = cor_conf.leer(C["base"], "n", sem_200)
    for c in ("huella", "sin_contra"):
        res[c]["ent"] = delta(cor_ent.leer(C[c], "n", sem_200), base_conf)
    # k6k y c05: todos los datos de conf1 (k6k 450; c05 150 de h1 + 450), como en la confirmación
    res["k6k"]["ent"] = delta(cor_conf.leer(C["k6k"], "n", sem_n), cor_conf.leer(C["base"], "n", sem_n))
    res["c05"]["ent"] = delta({**cor_conf.leer(C["c05"], "n", sem_n), **cor_h1.leer(C["c05"], "v", sem_h1)},
                              {**cor_conf.leer(C["base"], "n", sem_n), **cor_h1.leer(C["base"], "v", sem_h1)})
    veredicto, why = decidir(res)
    L = ["# Regla de elección de la versión final\n",
         "| config | Δ P(top 6) entrenamiento (IC 95 %) | Δ P(top 6) desconocido (IC 95 %) | falsos positivos de la huella |", "|---|---|---|---|"]
    f = lambda t: "—" if t is None else f"{100 * t[0]:+.1f} ({100 * t[1]:+.1f} a {100 * t[2]:+.1f})"
    L.append(f"| base | — | — | {res['base']['fp']:.1f} % |")
    for c in ("k6k", "c05", "sin_contra", "huella"):
        L.append(f"| {c} | {f(res[c].get('ent'))} | {f(res[c].get('desc'))} | {res[c]['fp']:.1f} % |")
    L.append("\n" + "\n".join(why))
    if isinstance(veredicto, tuple):
        L.append(f"\n**Pasan un arreglo ({veredicto[1]}) y un parámetro ({veredicto[2]}): lanzar la combinación f = {veredicto[2]} + {veredicto[1]} (≈ 1,2 h) "
                 "y adoptarla si no pierde contra cada uno por separado.**")
    elif veredicto == "base":
        L.append("\n**No pasa nada: la versión final es v1.3-limpers.**")
    else:
        L.append(f"\n**Versión final recomendada: {veredicto}.**")
    texto = "\n".join(L)
    open(os.path.join(d_desc, "decision.md"), "w", encoding="utf-8").write(texto)
    print(texto)


if __name__ == "__main__":
    main()
