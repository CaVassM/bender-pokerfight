#!/usr/bin/env python3
"""Capa 3, confirmación del paso 1: c05, c24 y «k6k» (v1.3-limpers con solo K = 6000) contra v1.3-limpers, con semillas NUEVAS.

Campo de entrenamiento de 28 (el mismo del halving, SIN darwin ni novato). 450 campeonatos nuevos por configuración
(semillas 10_000_000 + i) emparejados contra la base (v1.3-limpers, parámetros por defecto). Para c05 y c24 se suman los 150 campeonatos
de la validación de h1 (semillas 9_000_000 + i, no usadas para elegir): 150 + 450. k6k solo tiene los 450.

Regla (usuario): se adopta el candidato cuyo IC 95 % de Δ P(top 6) excluye el 0 a favor y que no sube la tasa de quiebra; si más de uno
cumple, el más simple (k6k antes que c05 o c24; entre c05 y c24, el de mayor Δ P(top 6)). Si se adopta: tag v1.4. Si ninguno: defaults intactos.
«No sube la tasa de quiebra» se aplica LITERAL al estimador puntual: Δ tasa de quiebra por mesa <= 0 (la métrica `tasa_quiebra` de
campeonato.py). Se informa también Δ P(quiebra) por campeonato (= -Δ P(sobrevivir)); si ambas discrepan en una ganadora, se avisa.

Se corre SIEMPRE desde un worktree de un commit fijo, exigiendo que el código de decisión sea el de v1.3-limpers:
  bender/.venv/Scripts/python.exe bender/pruebas/evaluar_fijo.py --referencia v1.3-limpers --script confirmacion.py -- --nombre conf1
Es reanudable (no repite campeonatos con resultado.json).
"""

import argparse
import json
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campeonato as CAMP  # noqa: E402
import evaluar as E  # noqa: E402
import halving as H  # noqa: E402

SEMILLA_NUEVA = 10_000_000
N_NUEVAS = 450
SEMILLA_VALID_H1 = H.SEMILLA_VALID           # 9_000_000: las 150 semillas de validación de h1
N_VALID_H1 = H.N_VALID
CANDIDATOS = ["k6k", "c24", "c05"]            # orden de sencillez para el desempate


def variantes():
    h1 = json.load(open(os.path.join(E.SALIDAS, "halving", "h1", "configuraciones.json"), encoding="utf-8"))["configuraciones"]
    por_id = {c["id"]: c for c in h1}
    return {"base": {"id": "base", "variante": {}},
            "k6k": {"id": "k6k", "variante": {"riesgo": {"K": 6000}}},
            "c05": {"id": "c05", "variante": por_id["c05"]["variante"]},
            "c24": {"id": "c24", "variante": por_id["c24"]["variante"]}}


def leer_mesas(cor, cfg, bloque, semillas):
    """{semilla: (quiebras de Bender, mesas jugadas por Bender)}: una quiebra = Bender termina la mesa con 0 fichas."""
    out = {}
    for s in semillas:
        ruta = os.path.join(cor.dir_cfg(cfg, bloque), f"t{s}", "resultado.json")
        if not os.path.exists(ruta):
            continue
        reg = CAMP.resumir_torneo(json.load(open(ruta, encoding="utf-8")))
        js = [j for j in reg["jugadas"] if j.get("tipo") == "bender"]
        out[s] = (sum(1 for j in js if j["despues"] == 0), len(js))
    return out


def ic_tasa(qa, qb, B=4000, semilla=5):
    """IC 95 % de (quiebras/mesas del candidato) − (quiebras/mesas de la base), remuestreando campeonatos (semillas) emparejados."""
    comunes = sorted(set(qa) & set(qb))
    if len(comunes) < 5:
        return (float("nan"),) * 3
    f = lambda idx: (sum(qa[comunes[i]][0] for i in idx) / max(1, sum(qa[comunes[i]][1] for i in idx))
                     - sum(qb[comunes[i]][0] for i in idx) / max(1, sum(qb[comunes[i]][1] for i in idx)))
    rng = random.Random(semilla)
    n = len(comunes)
    ms = sorted(f(rng.choices(range(n), k=n)) for _ in range(B))
    return f(range(n)), ms[int(0.025 * B)], ms[int(0.975 * B)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nombre", default="conf1")
    ap.add_argument("--paralelo", type=int, default=10)
    ap.add_argument("--nuevas", type=int, default=N_NUEVAS)
    ap.add_argument("--solo-informe", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")        # la consola de Windows (cp1252) no tiene Δ
    V = variantes()
    directorio = os.path.join(E.SALIDAS, "halving", args.nombre)
    os.makedirs(directorio, exist_ok=True)
    cor = H.Corredor(directorio, args.paralelo)
    cor_h1 = H.Corredor(os.path.join(E.SALIDAS, "halving", "h1"), 1)
    sem_n = [SEMILLA_NUEVA + i for i in range(args.nuevas)]
    sem_h1 = [SEMILLA_VALID_H1 + i for i in range(N_VALID_H1)]
    json.dump({"commit": os.environ.get("BENDER_COMMIT_COMPLETO"), "campo": H.CAMPO, "semillas_nuevas": [sem_n[0], sem_n[-1]],
               "variantes": V}, open(os.path.join(directorio, "configuraciones.json"), "w"), indent=1)
    t0 = time.time()
    if not args.solo_informe:
        cor.jugar([V["base"]] + [V[c] for c in CANDIDATOS], sem_n, "n", f"confirmación (base + 3 candidatos × {len(sem_n)} semillas nuevas)")

    def datos(cfg_id, acumulado):
        """Métricas por semilla: de las nuevas y (c05, c24 y la base) además de las 150 de la validación de h1."""
        cfg = V[cfg_id]
        d, q = cor.leer(cfg, "n", sem_n), leer_mesas(cor, cfg, "n", sem_n)
        if acumulado and cfg_id != "k6k":
            d.update(cor_h1.leer(cfg, "v", sem_h1))
            q.update(leer_mesas(cor_h1, cfg, "v", sem_h1))
        return d, q

    L = [f"# Confirmación «{args.nombre}» (commit {os.environ.get('BENDER_COMMIT')}; campo {H.CAMPO} + candidato; {(time.time() - t0) / 3600:.1f} h en esta corrida)\n"]
    resultados = {}
    for etiqueta, acumulado in (("ACUMULADAS (c05 y c24: 150 de h1 + nuevas; k6k: solo nuevas) — base de la decisión", True),
                                ("Solo semillas NUEVAS (comprobación)", False)):
        L.append(f"## {etiqueta}\n")
        L.append("| candidato | n | Δ P(top 6) pts (IC 95 %) | Δ P(sobrevivir) pts (IC 95 %) | Δ P(quiebra) por campeonato pts | Δ tasa de quiebra por mesa pts (IC 95 %) | Δ puesto medio (IC 95 %) | Δ bb/100 (IC 95 %) |")
        L.append("|---|---|---|---|---|---|---|---|")
        for c in CANDIDATOS:
            # La base se acumula con el MISMO conjunto de semillas que el candidato (solo las comunes cuentan al emparejar).
            bd, bq = datos("base", acumulado)
            d, q = datos(c, acumulado)
            e = H.emparejar(d, bd)
            if e["n"] == 0:
                continue
            m = {k: H.ic(e[k]) for k in ("top6", "sobrevive", "puesto", "bb100")}
            tq = ic_tasa(q, bq)
            resultados[(acumulado, c)] = {"n": e["n"], **m, "quiebra_mesa": tq}
            L.append(f"| {c} | {e['n']} | {100 * m['top6'][0]:+.1f} ({100 * m['top6'][1]:+.1f} a {100 * m['top6'][2]:+.1f}) | "
                     f"{100 * m['sobrevive'][0]:+.1f} ({100 * m['sobrevive'][1]:+.1f} a {100 * m['sobrevive'][2]:+.1f}) | "
                     f"{-100 * m['sobrevive'][0]:+.1f} | {100 * tq[0]:+.2f} ({100 * tq[1]:+.2f} a {100 * tq[2]:+.2f}) | "
                     f"{m['puesto'][0]:+.2f} ({m['puesto'][1]:+.2f} a {m['puesto'][2]:+.2f}) | {m['bb100'][0]:+.0f} ({m['bb100'][1]:+.0f} a {m['bb100'][2]:+.0f}) |")
        L.append("")

    # --- regla de adopción (sobre las semillas acumuladas) ---
    cumplen = []
    L.append("## Regla de adopción\n")
    for c in CANDIDATOS:
        r = resultados.get((True, c))
        if not r:
            continue
        top_ok = r["top6"][1] > 0
        quiebra_ok = r["quiebra_mesa"][0] <= 0
        camp_ok = -r["sobrevive"][0] <= 0
        L.append(f"- {c}: IC de Δ P(top 6) excluye el 0 a favor: {'sí' if top_ok else 'no'}; Δ tasa de quiebra por mesa <= 0: "
                 f"{'sí' if quiebra_ok else 'no'}; (Δ P(quiebra) por campeonato <= 0: {'sí' if camp_ok else 'no'})")
        if top_ok and quiebra_ok:
            cumplen.append((c, camp_ok))
    if cumplen:
        simples = [c for c in CANDIDATOS if c in dict(cumplen)]
        orden = ["k6k"] + sorted([c for c in simples if c != "k6k"], key=lambda c: -resultados[(True, c)]["top6"][0])
        elegido = [c for c in orden if c in simples][0]
        L.append(f"\n**Cumplen la regla: {', '.join(c for c, _ in cumplen)}. Se adopta el más simple: {elegido}** (tag v1.4; aplicar a los defaults y pasar las pruebas).")
        if not dict(cumplen)[elegido]:
            L.append("AVISO: la tasa de quiebra por campeonato (= -Δ P(sobrevivir)) SÍ sube en este candidato aunque la de por mesa no: decisión del usuario.")
        L.append("\n```json\n" + json.dumps(V[elegido]["variante"], indent=1) + "\n```")
    else:
        L.append("\n**Ningún candidato cumple la regla: los defaults (v1.3-limpers) no cambian.**")
    texto = "\n".join(L)
    open(os.path.join(directorio, "informe.md"), "w", encoding="utf-8").write(texto)
    print(texto)


if __name__ == "__main__":
    main()
