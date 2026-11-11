#!/usr/bin/env python3
"""Compara las versiones de riesgo de Bender con la métrica del campeonato y con las mesas de 5, TODO desde un commit fijo.

Configuraciones (las variantes están en pruebas/variantes/riesgo/):
  v1        = el código de siempre (utilidad apagada, calibración apagada)  <- referencia (= v1-probabilistico)
  cal       = solo la calibración de los all-in
  u5k u10k u20k u40k           = utilidad ln(S+K) con K = 5 000 / 10 000 / 20 000 / 40 000
  u5k-cal u10k-cal u20k-cal u40k-cal  = lo mismo con la calibración

Dos flujos independientes (se pueden correr a la vez):
  --flujo campeonatos : `campeonato.py` (formato real: 10 rondas, mesas de 5-6, fichas que se arrastran, eliminación en 0)
  --flujo mesas       : `evaluar.py --solo-mesa` (mesas de 5 a 10 000 fichas, 50 manos: bb/100 y tasa de quiebra por mesa)

Solo rivales de ENTRENAMIENTO (aleatorio, conservador, base, estadistico, bandido, espia): darwin y novato (reserva) no
se usan para elegir K. Reanudable: un campeonato o una evaluación ya guardados no se repiten.

  bender/.venv/Scripts/python.exe bender/pruebas/comparar_riesgo.py --flujo campeonatos --commit <hash> --torneos 300
"""

import argparse
import os
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
FIJO = os.path.join(AQUI, "evaluar_fijo.py")
VARIANTES = os.path.join(AQUI, "variantes", "riesgo")
ORDEN = ["v1", "cal", "u10k", "u10k-cal", "u5k", "u5k-cal", "u20k", "u20k-cal", "u40k", "u40k-cal"]
ENTRENAMIENTO = "aleatorio,conservador,base,estadistico,bandido,espia"


def correr(cmd, salida):
    t0 = time.time()
    with open(salida, "w", encoding="utf-8") as f:
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, text=True)
    return r.returncode, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flujo", choices=["campeonatos", "mesas"], required=True)
    ap.add_argument("--commit", required=True, help="commit fijo desde el que se evalúa")
    ap.add_argument("--torneos", type=int, default=300)
    ap.add_argument("--mesas", type=int, default=600)
    ap.add_argument("--paralelo", type=int, default=8)
    ap.add_argument("--configs", default=",".join(ORDEN))
    ap.add_argument("--mensajes-en", default="v1,cal", help="configuraciones de mesas con log completo (para riesgo_ev.py)")
    args = ap.parse_args()
    dir_salida = os.path.join(AQUI, "salidas", "comparar")
    os.makedirs(dir_salida, exist_ok=True)
    for nombre in args.configs.split(","):
        variante = os.path.join(VARIANTES, nombre + ".json")
        if args.flujo == "campeonatos":
            etiqueta = f"riesgo-{nombre}"
            cmd = [PY, FIJO, "--commit", args.commit, "--script", "campeonato.py", "--", "--etiqueta", etiqueta, "--params", variante,
                   "--torneos", str(args.torneos), "--paralelo", str(args.paralelo)]
            if nombre != "v1":
                cmd += ["--comparar", "riesgo-v1"]
        else:
            etiqueta = f"riesgo-mesas-{nombre}"
            cmd = [PY, FIJO, "--commit", args.commit, "--", "--etiqueta", etiqueta, "--params", variante, "--rivales", ENTRENAMIENTO,
                   "--solo-mesa", "--mesas", str(args.mesas), "--rondas", "50", "--paralelo", str(args.paralelo)]
            if nombre in args.mensajes_en.split(","):
                cmd += ["--mensajes"]
            if nombre != "v1":
                cmd += ["--comparar", "riesgo-mesas-v1"]
        salida = os.path.join(dir_salida, f"{etiqueta}.txt")
        print(f"[{args.flujo}] {nombre} ...", flush=True)
        rc, dt = correr(cmd, salida)
        print(f"[{args.flujo}] {nombre}: código {rc}, {dt / 60:.1f} min -> {salida}", flush=True)
        if rc != 0:
            print(open(salida, encoding="utf-8").read()[-1500:], flush=True)


if __name__ == "__main__":
    main()
