#!/usr/bin/env python3
"""¿El código actual, con los interruptores apagados, decide EXACTAMENTE lo mismo que el tag?

Genera N spots al azar (semilla fija; preflop y postflop, 1-4 rivales, con y sin apuesta enfrentada, stacks cortos y
profundos), decide cada uno con Capa1 de DOS carpetas de bender (el worktree del tag y la actual) con las mismas
semillas, y compara la acción y el EV de cada opción. Los interruptores nuevos (riesgo.utilidad, calibracion_allin.activa)
estaban apagados por defecto hasta v1.1-riesgo (la utilidad ahora viene ENCENDIDA): para comparar con v1-probabilistico hay que
pasar --params pruebas/variantes/riesgo/v1.json (utilidad apagada), y entonces tiene que dar lo mismo.

  bender/.venv/Scripts/python.exe bender/pruebas/equivalencia_tag.py --tag-dir <worktree del tag>/bender --n 300 --params <v1.json>
"""

import argparse
import json
import os
import random
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
ACTUAL = os.path.dirname(AQUI)


def generar(dir_bender, n, semilla, salida, params_json):
    """Modo hijo: decide los spots con el código de `dir_bender` y escribe un JSON."""
    sys.path.insert(0, dir_bender)
    import cartas as C
    from capa1 import Capa1
    from estado import EstadoPublico, Jugador, Turno
    from params import cargar_params

    class Mesa:
        manos_mesa, segundos_mesa = 0, 0.0

    rng = random.Random(semilla)
    p = cargar_params(params_json)
    p["reloj"].update({"n_min": 600, "eps_obj": 0.01})
    p["capa1"]["semilla"] = 7
    out = []
    for k in range(n):
        n_board = rng.choice([0, 3, 4, 5])
        cartas = rng.sample(range(52), 2 + n_board)
        mano, board = cartas[:2], cartas[2:]
        n_riv = rng.choice([1, 2, 3, 4])
        saldo_yo = rng.choice([900, 1500, 2500, 6000, 10_000, 14_000])
        yo_ap = rng.choice([0, 0, 50, 100])
        apuesta = rng.choice([0, 0, 100, 300, 800, 3000])
        riv = []
        for _ in range(n_riv):
            ap = apuesta if apuesta and rng.random() < 0.8 else rng.choice([0, 100])
            riv.append((rng.choice([0, 800, 3000, 10_000]), ap))
        pozo = max(150, yo_ap + sum(a for _, a in riv) + rng.choice([0, 300, 1200]))
        jug = [Jugador(id="yo", saldo=saldo_yo, apuesta_ronda=yo_ap, activo=True, en_torneo=True, en_mano=True, silla=0)]
        for i, (s, a) in enumerate(riv):
            jug.append(Jugador(id=f"r{i}", saldo=s, apuesta_ronda=a, activo=True, en_torneo=True, en_mano=True, silla=i + 1, allin=(s == 0)))
        etapa = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}[n_board]
        ap_actual = max([a for _, a in riv] + [yo_ap])
        hist = [{"id_jugador": f"r{i}", "etapa": etapa, "accion": {"tipo": "raise" if ap_actual else "check"}} for i in range(n_riv)] if ap_actual else []
        est = EstadoPublico(id_mano="m", etapa=etapa, comunitarias=[C.a_tupla(c) for c in board], pozo=pozo, apuesta_actual=ap_actual,
                            subida_minima=100, ciega_chica=50, ciega_grande=100, boton=rng.randrange(6), jugadores=jug, historial=hist)
        c = max(0, ap_actual - yo_ap)
        validas = ["fold", "check" if c == 0 else "call"]
        if saldo_yo + yo_ap >= ap_actual + 100:
            validas.append("bet" if c == 0 else "raise")
        if saldo_yo > 0:
            validas.append("allin")
        turno = Turno(est, "yo", [C.a_tupla(x) for x in mano], validas)
        if not turno.rivales:
            continue
        capa = Capa1(p, rng=random.Random(1000 + k))
        try:
            accion, motivo, info = capa.decidir(turno, Mesa())
            out.append({"k": k, "accion": accion, "evs": [(f["accion"], f["ev"], f["descartada"]) for f in info.get("tabla_ev", [])],
                        "elegida": info.get("elegida")})
        except Exception as e:                                   # noqa: BLE001
            out.append({"k": k, "error": repr(e)})
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(out, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag-dir", help="carpeta bender/ del worktree del tag")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--semilla", type=int, default=424242)
    ap.add_argument("--params", default=None, help="JSON de parámetros para el código ACTUAL (por defecto, los de params.py)")
    ap.add_argument("--hijo", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--salida", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.hijo:
        generar(args.hijo, args.n, args.semilla, args.salida, args.params)
        return
    tmp = os.environ.get("TEMP", ".")
    salidas = {}
    for nombre, d, pj in (("tag", args.tag_dir, None), ("actual", ACTUAL, args.params)):
        ruta = os.path.join(tmp, f"equiv_{nombre}.json")
        cmd = [sys.executable, os.path.abspath(__file__), "--hijo", d, "--n", str(args.n), "--semilla", str(args.semilla), "--salida", ruta]
        if pj:
            cmd += ["--params", pj]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"falló {nombre}: {r.stderr[-800:]}")
        salidas[nombre] = json.load(open(ruta, encoding="utf-8"))
    a, b = salidas["tag"], salidas["actual"]
    dif_acc = dif_ev = 0
    for x, y in zip(a, b):
        if x.get("accion") != y.get("accion") or x.get("error") != y.get("error"):
            dif_acc += 1
            continue
        for (n1, e1, d1), (n2, e2, d2) in zip(x.get("evs", []), y.get("evs", [])):
            if n1 != n2 or abs(e1 - e2) > 0.05 or d1 != d2:
                dif_ev += 1
                break
    print(f"spots comparados: {len(a)} vs {len(b)}; acciones distintas: {dif_acc}; spots con algún EV/descarte distinto: {dif_ev}; "
          f"errores tag/actual: {sum('error' in x for x in a)}/{sum('error' in x for x in b)}")
    sys.exit(0 if (dif_acc == 0 and dif_ev == 0 and len(a) == len(b)) else 1)


if __name__ == "__main__":
    main()
