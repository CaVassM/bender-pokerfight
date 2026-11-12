"""Los bots de estrés siempre devuelven una acción válida y hacen lo que dicen."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "bots_estres"))
from estres import accion  # noqa: E402


class Con:
    id_jugador = "yo"


def msg(validas, actual=0, sub_min=100, saldo=10_000, ap_ronda=0):
    return {"acciones_validas": validas,
            "estado": {"apuesta_actual": actual, "subida_minima": sub_min,
                       "jugadores": [{"id": "yo", "saldo": saldo, "apuesta_ronda": ap_ronda}]}}


def test_allin_siempre():
    assert accion("allin", msg(["fold", "call", "raise", "allin"], 300), Con) == {"tipo": "allin"}
    assert accion("allin", msg(["fold", "call"], 300), Con) == {"tipo": "call"}          # sin all-in válido: iguala


def test_iguala_siempre():
    assert accion("iguala", msg(["fold", "call", "raise", "allin"], 300), Con) == {"tipo": "call"}
    assert accion("iguala", msg(["check", "bet", "allin"]), Con) == {"tipo": "check"}


def test_sube_el_minimo():
    assert accion("sube_min", msg(["check", "bet", "allin"], 0, 100), Con) == {"tipo": "bet", "monto": 100}
    assert accion("sube_min", msg(["fold", "call", "raise", "allin"], 300, 200), Con) == {"tipo": "raise", "monto": 500}
    # si la subida mínima llega al stack: all-in; si no se puede subir: iguala
    assert accion("sube_min", msg(["fold", "call", "raise", "allin"], 300, 200, saldo=400), Con) == {"tipo": "allin"}
    assert accion("sube_min", msg(["fold", "call"], 300, 200), Con) == {"tipo": "call"}
