#!/usr/bin/env python3
"""¿Dónde se va el tiempo de una mano y cuántas manos/s se pueden lograr? (pendiente 4, para la Capa 3)

Mide con bin/mesa (la misma mesa del torneo, 5 jugadores, ciegas 50/100, stack 10 000, plazo 5 s):

  A) Un bot a la vez: mesas con 5 copias del MISMO bot (tokens distintos). El tiempo por mano de cada
     bot sale de ahí (mesa + comunicación + decisión de ese bot). Los bots instantáneos
     (aleatorio, conservador) dan el piso: lo que cuesta la mesa y la red local sin pensar.
  B) Escalado: K mesas en paralelo con la mezcla [bender, base, estadistico, espia, bandido]; manos/s
     totales y por mesa para K = 1, 2, 4, 8, 12, 16, 24. Dice cuántos núcleos rinden.

El tiempo de juego se mide desde que se conecta el último bot hasta que la mesa termina (sin contar el
arranque de procesos).  Uso: bender/.venv/Scripts/python.exe bender/pruebas/throughput.py [--rondas 200]
"""

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIN = os.path.join(RAIZ, "bin")
EXE = ".exe" if os.name == "nt" else ""
BENDER_MAIN = os.path.join(RAIZ, "bender", "main.py")
SALIDA = os.path.join(RAIZ, "bender", "pruebas", "salidas", "throughput")
EXTRA = {"estadistico": ["-simulaciones", "2000"], "bandido": ["-silencioso"], "espia": ["-silencioso"], "darwin": ["-silencioso"]}


def params_bender(dir_run):
    os.makedirs(dir_run, exist_ok=True)
    ruta = os.path.join(dir_run, "params.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({"registro": {"mensajes": False}, "rivales": {"persistir": False}}, f)
    return ruta


def correr_mesa(indice, bots, rondas, puerto, dir_run):
    """Una mesa con los bots dados. Devuelve (manos jugadas, segundos de juego)."""
    os.makedirs(dir_run, exist_ok=True)
    abiertos, procesos = [], []

    def lanzar(cmd, nombre, env=None):
        out = open(os.path.join(dir_run, nombre + ".out"), "w", encoding="utf-8")
        abiertos.append(out)
        p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, cwd=RAIZ, env=env)
        procesos.append(p)
        return p

    mesa = lanzar([os.path.join(BIN, "mesa" + EXE), "-addr", f"127.0.0.1:{puerto}", "-jugadores", "6", "-min-jugadores", "5",
                   "-rondas", str(rondas), "-stack", "10000", "-ciega-chica", "50", "-ciega-grande", "100",
                   "-timeout-ms", "5000", "-id", f"t{indice}"], "mesa")
    ruta_mesa = os.path.join(dir_run, "mesa.out")
    for _ in range(100):
        time.sleep(0.1)
        if "escuchando" in open(ruta_mesa, encoding="utf-8", errors="replace").read():
            break
    ruta_p = params_bender(dir_run)
    for i, bot in enumerate(bots):
        if bot == "bender":
            env = dict(os.environ, BENDER_TOKEN=f"bender-{indice}-{i}")
            lanzar([sys.executable, BENDER_MAIN, "-addr", f"127.0.0.1:{puerto}", "-silencioso",
                    "-log", os.path.join(dir_run, f"bender{i}.jsonl"), "-params", ruta_p], f"bender{i}", env)
        else:
            lanzar([os.path.join(BIN, bot + EXE), "-addr", f"127.0.0.1:{puerto}", "-token", f"k-{bot}-{i}"] + EXTRA.get(bot, []), f"{bot}{i}")
        time.sleep(0.15)
    # El juego arranca cuando se conecta el último bot (mínimo 5): se cuenta desde ahora.
    inicio = time.time()
    try:
        mesa.wait(timeout=1200)
    except subprocess.TimeoutExpired:
        pass
    segundos = time.time() - inicio
    for p in procesos:
        if p.poll() is None:
            p.kill()
    for a in abiertos:
        a.close()
    texto = open(ruta_mesa, encoding="utf-8", errors="replace").read()
    manos = 0
    for linea in texto.splitlines():
        if "partida terminada" in linea:
            manos = int(linea.split(",")[1].split()[0])
    return manos, segundos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rondas", type=int, default=200)
    ap.add_argument("--puerto-base", type=int, default=9600)
    ap.add_argument("--solo", choices=["A", "B"], default=None)
    ap.add_argument("--ks", default="1,2,4,8,12,16,24", help="mesas en paralelo a probar en B")
    ap.add_argument("--mezcla", default="bender,base,estadistico,espia,bandido", help="bots de cada mesa en B")
    ap.add_argument("--etiqueta", default="")
    args = ap.parse_args()
    os.makedirs(SALIDA, exist_ok=True)
    resultado = {"A": {}, "B": {}}
    puerto = args.puerto_base

    if args.solo in (None, "A"):
        print("## A) Un bot a la vez: 5 copias del mismo bot, una mesa (sin otra carga en la máquina)\n")
        print("| bot | manos | segundos | manos/s | ms por mano |")
        print("|---|---|---|---|---|")
        for bot in ["aleatorio", "conservador", "base", "estadistico", "bandido", "espia", "bender", "darwin"]:
            manos, seg = correr_mesa(0, [bot] * 5, args.rondas, puerto, os.path.join(SALIDA, f"A-{bot}"))
            puerto += 1
            if manos:
                resultado["A"][bot] = {"manos": manos, "segundos": seg, "manos_por_s": manos / seg}
                print(f"| {bot} | {manos} | {seg:.1f} | {manos / seg:.1f} | {1000 * seg / manos:.0f} |", flush=True)
            else:
                print(f"| {bot} | (la mesa no terminó) | | | |", flush=True)

    if args.solo in (None, "B"):
        print("\n## B) Escalado: K mesas en paralelo con [bender, base, estadistico, espia, bandido]\n")
        print("| mesas en paralelo | manos totales | segundos | manos/s totales | manos/s por mesa |")
        print("|---|---|---|---|---|")
        mezcla = args.mezcla.split(",")
        print(f"(mezcla: {mezcla})")
        for k in [int(x) for x in args.ks.split(",")]:
            inicio = time.time()
            with ThreadPoolExecutor(k) as pool:
                futuros = [pool.submit(correr_mesa, i, mezcla, args.rondas, puerto + i,
                                       os.path.join(SALIDA, f"B{args.etiqueta}-{k}-{i}")) for i in range(k)]
                res = [f.result() for f in futuros]
            puerto += k
            manos = sum(m for m, _ in res)
            seg = max(s for _, s in res)
            resultado["B"][k] = {"manos": manos, "segundos": seg, "manos_por_s": manos / seg}
            print(f"| {k} | {manos} | {seg:.1f} | {manos / seg:.1f} | {manos / seg / k:.1f} |", flush=True)

    with open(os.path.join(SALIDA, f"resultado{args.etiqueta}.json"), "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=1)


if __name__ == "__main__":
    main()
