#!/usr/bin/env python3
"""Paso 3 (único, pedido por el usuario el 2026-11-17): confirmación de la versión final con darwin y novato EN EL CAMPO.

  A = v1.3-limpers  (los parámetros de v1.3: riesgo.K = 10 000; el resto de los defaults no cambió)
  B = final         (defaults actuales de params.py: riesgo.K = 6 000 = k6k)

Campo de 28 (27 + Bender): el de entrenamiento con dos de los tres `bender_v1` reemplazados por una `darwin` y un `novato`:
  aleatorio:4,conservador:4,base:4,estadistico:4,bandido:4,espia:4,bender_v1:1,darwin:1,novato:1
300 semillas NUEVAS (17 000 000 + i), emparejadas por semilla. darwin y novato son rivales de RESERVA: solo se usan aquí, nunca para elegir.

REGLA (del usuario): si B NO sale significativamente peor que A en P(top 6) ni en P(sobrevivir) (límite superior del IC 95 % < 0 = peor),
se etiqueta v1.4-final; si sale significativamente peor, no se etiqueta y se avisa.

  bender/.venv/Scripts/python.exe bender/pruebas/evaluar_fijo.py --script paso3_eval.py -- --nombre f3
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bandido_eval as BE  # noqa: E402
import campeonato as CAMP  # noqa: E402
import evaluar as E  # noqa: E402
import halving as H  # noqa: E402

SEMILLA = 17_000_000
CAMPO_FINAL = "aleatorio:4,conservador:4,base:4,estadistico:4,bandido:4,espia:4,bender_v1:1,darwin:1,novato:1"
CFG_A = {"id": "v13_limpers", "variante": {"riesgo": {"K": 10_000}}}
CFG_B = {"id": "final", "variante": {}}


def peor_significativo(t):
    return t is not None and t[2] < 0


def veredicto(top6, surv):
    """True = se etiqueta (B no sale significativamente peor en P(top 6) ni en P(sobrevivir))."""
    return not (peor_significativo(top6) or peor_significativo(surv))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nombre", default="f3")
    ap.add_argument("--paralelo", type=int, default=10)
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--solo-informe", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    directorio = os.path.join(E.SALIDAS, "halving", args.nombre)
    os.makedirs(directorio, exist_ok=True)
    json.dump({"commit": os.environ.get("BENDER_COMMIT_COMPLETO"), "campo": CAMPO_FINAL, "A": CFG_A, "B": CFG_B},
              open(os.path.join(directorio, "configuraciones.json"), "w"), indent=1)
    cor = H.Corredor(directorio, args.paralelo)
    cor.campo = CAMP.campo_de(CAMPO_FINAL)
    sem = [SEMILLA + i for i in range(args.n)]
    t0 = time.time()
    if not args.solo_informe:
        cor.jugar([CFG_A, CFG_B], sem, "n", f"PASO 3: v1.3-limpers vs final × {args.n} semillas nuevas (con darwin y novato)")

    L = [f"# Paso 3: confirmación con darwin y novato (commit {os.environ.get('BENDER_COMMIT')}; {(time.time() - t0) / 3600:.1f} h en esta corrida)\n",
         f"Campo: {CAMPO_FINAL} + Bender; semillas {SEMILLA}+i ({args.n} previstas). A = v1.3-limpers (K = 10 000); B = final (K = 6 000).\n",
         "Absolutos:\n\n| config | n | P(top 6) | P(sobrevivir) | puesto medio |\n|---|---|---|---|---|"]
    BE.absolutos(L, cor, CFG_A, "n", sem, "A (v1.3-limpers)")
    BE.absolutos(L, cor, CFG_B, "n", sem, "B (final)")
    L.append("")
    L += [h.replace("| selector |", "| config |") for h in BE.CABECERA]
    filas = []
    BE.tabla(filas, "B (final)", cor, CFG_B, "n", [("A (v1.3-limpers)", cor, CFG_A, "n")], sem)
    L += [f.replace("| selector | contra |", "| config | contra |") for f in filas]
    e = H.emparejar(cor.leer(CFG_B, "n", sem), cor.leer(CFG_A, "n", sem))
    L.append("")
    if e["n"]:
        top6, surv = H.ic(e["top6"]), H.ic(e["sobrevive"])
        ok = veredicto(top6, surv)
        L.append(f"Δ P(top 6) = {100 * top6[0]:+.1f} ({100 * top6[1]:+.1f} a {100 * top6[2]:+.1f}); Δ P(sobrevivir) = {100 * surv[0]:+.1f} "
                 f"({100 * surv[1]:+.1f} a {100 * surv[2]:+.1f}) con n = {e['n']}.")
        L.append("\n**" + ("B NO sale significativamente peor en P(top 6) ni en P(sobrevivir): se etiqueta v1.4-final." if ok else
                           "B sale SIGNIFICATIVAMENTE PEOR en P(top 6) o en P(sobrevivir): NO se etiqueta; avisar al usuario.") + "**")
    else:
        L.append("(sin datos emparejados)")
    texto = "\n".join(L)
    open(os.path.join(directorio, "informe.md"), "w", encoding="utf-8").write(texto)
    print(texto)


if __name__ == "__main__":
    main()
