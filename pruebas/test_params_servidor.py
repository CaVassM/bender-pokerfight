"""params_servidor.json (reintentos de conexión de 6 h para el día del torneo): `-params` mezcla, no reemplaza."""

import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
BENDER = os.path.dirname(AQUI)
sys.path.insert(0, BENDER)

from params import cargar_params  # noqa: E402

RUTA = os.path.join(BENDER, "params_servidor.json")
CLAVES = {"inicial_s", "caida_s", "fin_s"}


def test_el_archivo_solo_toca_los_reintentos_de_conexion():
    with open(RUTA, encoding="utf-8") as f:
        d = json.load(f)
    assert set(d) == {"conexion"}
    assert set(d["conexion"]) == CLAVES
    assert all(v == 21600.0 for v in d["conexion"].values())


def test_mezclar_no_borra_los_otros_parametros_de_conexion():
    base, p = cargar_params(), cargar_params(RUTA)
    for k in CLAVES:
        assert p["conexion"][k] == 21600.0
    # los demás parámetros de conexión (espera_max_s, timeout_saludo_s, keepalive_s...) siguen con su valor
    otros = set(base["conexion"]) - CLAVES
    assert {"espera_max_s", "timeout_saludo_s", "keepalive_s"} <= otros
    for k in otros:
        assert p["conexion"][k] == base["conexion"][k]
    # y nada fuera de esas tres claves cambió
    p["conexion"].update({k: base["conexion"][k] for k in CLAVES})
    assert p == base
