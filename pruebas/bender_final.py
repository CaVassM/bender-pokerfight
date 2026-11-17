#!/usr/bin/env python3
"""Lanzador de Bender para la simulación de la final (final_sim.py, config e): igual que main.py, pero después de cargar los
parámetros inyecta la sección `bandido` del JSON que indica BENDER_BRAZOS. El validador de params.py solo admite brazos con los
nombres de siempre (base, c05, c24) y claves que ya existan en ellos, así que los brazos a/b/d de la final no se pueden pasar por -params.
No cambia ningún valor por defecto ni el código de decisión: solo es una forma de pasar parámetros."""
import json
import os
import runpy
import sys

BENDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BENDER)
import params as P  # noqa: E402

_original = P.cargar_params


def _cargar(ruta=None):
    p = _original(ruta)
    ruta_brazos = os.environ.get("BENDER_BRAZOS")
    if ruta_brazos:
        with open(ruta_brazos, encoding="utf-8") as f:
            p["bandido"].update(json.load(f))
    return p


P.cargar_params = _cargar
sys.argv[0] = os.path.join(BENDER, "main.py")
runpy.run_path(sys.argv[0], run_name="__main__")
