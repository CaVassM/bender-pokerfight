#!/usr/bin/env python3
"""Prueba de integración con una mesa local en las condiciones del torneo.

Levanta bin/mesa (6 sillas, mínimo 5, 50 rondas, stack 10 000, ciegas 50/100,
plazo 5 s), sienta a 4 bots del kit con tokens fijos y a Bender, y espera a que
la mesa termine. Con --kill-tras-manos N, mata a Bender después de N manos y lo
relanza con el mismo token para comprobar que retoma su silla.

Uso (desde la raíz del kit, con el venv):
    bender/.venv/Scripts/python.exe bender/pruebas/mesa_local.py --rondas 50 --kill-tras-manos 15
"""

import argparse
import json
import os
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIN = os.path.join(RAIZ, "bin")
EXE = ".exe" if os.name == "nt" else ""
BENDER_MAIN = os.path.join(RAIZ, "bender", "main.py")
RETARDO_S = 0.0
RIVALES = [("base", []), ("conservador", []), ("aleatorio", []), ("estadistico", ["-simulaciones", "2000"])]


def lanzar(comando, salida, nombre, env=None):
    out = open(os.path.join(salida, f"{nombre}.out"), "w", encoding="utf-8")
    return subprocess.Popen(comando, stdout=out, stderr=subprocess.STDOUT, cwd=RAIZ, env=env), out


def leer_jsonl(ruta):
    if not os.path.exists(ruta):
        return []
    registros = []
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            try:
                registros.append(json.loads(linea))
            except ValueError:
                pass
    return registros


def manos_terminadas(ruta):
    return sum(1 for r in leer_jsonl(ruta) if r.get("tipo") == "mano_fin")


def lanzar_bender(puerto, salida, nombre, token):
    env = dict(os.environ, BENDER_TOKEN=token)       # el token entra por variable de entorno
    comando = [sys.executable, BENDER_MAIN, "-addr", f"127.0.0.1:{puerto}",
               "-log", os.path.join(salida, f"{nombre}.jsonl"), "-silencioso"]
    if RETARDO_S > 0:
        ruta_params = os.path.join(salida, "params-prueba.json")
        with open(ruta_params, "w", encoding="utf-8") as f:
            json.dump({"debug": {"retardo_s": RETARDO_S}}, f)
        comando += ["-params", ruta_params]
    return lanzar(comando, salida, nombre, env)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", type=int, default=9100)
    ap.add_argument("--rondas", type=int, default=50)
    ap.add_argument("--kill-tras-manos", type=int, default=0)
    ap.add_argument("--salida", default=None)
    ap.add_argument("--timeout-s", type=int, default=600)
    ap.add_argument("--retardo-s", type=float, default=0.0, help="pausa artificial de Bender por decisión")
    args = ap.parse_args()
    global RETARDO_S
    RETARDO_S = args.retardo_s

    salida = args.salida or os.path.join(RAIZ, "bender", "pruebas", "salidas", time.strftime("mesa-%Y%m%d-%H%M%S"))
    os.makedirs(salida, exist_ok=True)
    procesos = []
    token_bender = "bender-local"

    mesa, mesa_out = lanzar([os.path.join(BIN, "mesa" + EXE), "-addr", f"127.0.0.1:{args.puerto}", "-jugadores", "6",
                             "-min-jugadores", "5", "-rondas", str(args.rondas), "-stack", "10000",
                             "-ciega-chica", "50", "-ciega-grande", "100", "-timeout-ms", "5000"], salida, "mesa")
    procesos.append(mesa)
    ruta_mesa = os.path.join(salida, "mesa.out")
    for _ in range(100):
        time.sleep(0.1)
        if "escuchando" in open(ruta_mesa, encoding="utf-8", errors="replace").read():
            break
    else:
        print("la mesa no arrancó:", open(ruta_mesa, encoding="utf-8", errors="replace").read())
        return 1

    for nombre, extra in RIVALES:
        p, _ = lanzar([os.path.join(BIN, nombre + EXE), "-addr", f"127.0.0.1:{args.puerto}", "-token", f"k-{nombre}"] + extra,
                      salida, nombre)
        procesos.append(p)
    bender, _ = lanzar_bender(args.puerto, salida, "bender-1", token_bender)
    t0 = time.time()
    relanzado = False

    try:
        while mesa.poll() is None:
            if time.time() - t0 > args.timeout_s:
                print("TIMEOUT: la mesa no terminó")
                break
            if args.kill_tras_manos and not relanzado and manos_terminadas(os.path.join(salida, "bender-1.jsonl")) >= args.kill_tras_manos:
                print(f"[prueba] matando a Bender tras {args.kill_tras_manos} manos")
                bender.kill()
                bender.wait()
                time.sleep(1.5)
                bender, _ = lanzar_bender(args.puerto, salida, "bender-2", token_bender)
                relanzado = True
            time.sleep(0.3)
        duracion = time.time() - t0
    finally:
        for p in procesos + [bender]:
            if p.poll() is None:
                p.kill()

    # --- Informe ---
    print(f"\n== Mesa terminada en {duracion:.0f} s ==")
    texto_mesa = open(ruta_mesa, encoding="utf-8", errors="replace").read()
    resumen = [l for l in texto_mesa.splitlines() if l.startswith("Mesa [") or l.strip().startswith("#")]
    print("\n".join(resumen))
    sospechosas = [l for l in texto_mesa.splitlines() if any(k in l.lower() for k in ("timeout", "inválid", "invalid", "descart", "error"))]
    print(f"líneas de la mesa con timeout/inválida/error: {len(sospechosas)}")
    for l in sospechosas[:15]:
        print("   ", l)

    sesiones = ["bender-1"] + (["bender-2"] if relanzado else [])
    sillas = []
    for nombre in sesiones:
        regs = leer_jsonl(os.path.join(salida, nombre + ".jsonl"))
        decisiones = [r for r in regs if r.get("tipo") == "decision"]
        conex = [r for r in regs if r.get("tipo") == "conexion"]
        errores = [r for r in regs if r.get("tipo") in ("error", "accion_invalida")]
        sillas += [c["silla"] for c in conex]
        maximo = max((d["tiempo_s"] for d in decisiones), default=0)
        sin_cartas = sum(1 for d in decisiones if "sin cartas" in d.get("motivo", ""))
        print(f"{nombre}: {len(decisiones)} decisiones, {manos_terminadas(os.path.join(salida, nombre + '.jsonl'))} manos vistas, "
              f"{len(errores)} errores/inválidas, {sin_cartas} sin cartas, tiempo máx {maximo:.3f} s, conexiones: {[(c['silla'], c['reconexion']) for c in conex]}")
    if relanzado:
        print("Silla recuperada tras el kill:", "SÍ" if len(set(sillas)) == 1 else f"NO {sillas}")

    # Cómo se define P (§0): ¿pozo == suma de apuesta_ronda en preflop?
    regs = leer_jsonl(os.path.join(salida, "bender-1.jsonl"))
    muestras = {}
    for r in regs:
        if r.get("tipo") == "msg" and r["msg"].get("tipo") == "solicitar_accion":
            e = r["msg"]["estado"]
            suma = sum(j["apuesta_ronda"] for j in e["jugadores"])
            muestras.setdefault(e["etapa"], []).append((e["pozo"], suma))
    for etapa, lista in muestras.items():
        iguales = sum(1 for p, s in lista if p == s)
        print(f"pozo == suma(apuesta_ronda) en {etapa}: {iguales}/{len(lista)}; ejemplos (pozo, suma): {lista[:4]}")
    print(f"\nSalidas en {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
