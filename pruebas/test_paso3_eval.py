"""paso3_eval.py: A = K 10 000 y B = defaults (K 6 000), campo con darwin y novato, semillas nuevas, regla del tag."""

import json

import paso3_eval as P3
from params import _mezclar, cargar_params


def test_a_es_k_10000_y_b_son_los_defaults_actuales_con_k_6000():
    a, b = cargar_params(), cargar_params()
    _mezclar(a, json.loads(json.dumps(P3.CFG_A["variante"])))
    assert a["riesgo"]["K"] == 10_000 and b["riesgo"]["K"] == 6_000 and P3.CFG_B["variante"] == {}


def test_el_campo_son_28_con_darwin_y_novato_y_bender():
    import campeonato as CAMP
    campo = dict(CAMP.campo_de(P3.CAMPO_FINAL))
    assert sum(campo.values()) + 1 == 28 and campo["darwin"] == 1 and campo["novato"] == 1


def test_las_semillas_son_nuevas():
    import bandido_eval as BE
    import confirmacion as CONF
    import final2_eval as F2
    import final_eval as FE
    import halving as H
    usadas = [H.SEMILLA_RONDAS, H.SEMILLA_VALID, CONF.SEMILLA_NUEVA, BE.SEMILLA_DESC, 12_000_000, FE.SEMILLA_DESC, F2.SEMILLA_ENT, F2.SEMILLA_DESC]
    assert all(abs(P3.SEMILLA - u) >= 1_000_000 for u in usadas)


def test_regla_del_tag_solo_se_niega_si_el_limite_superior_es_negativo():
    t = lambda m, lo, hi: (m / 100, lo / 100, hi / 100)
    assert P3.veredicto(t(-3, -9, 3), t(-2, -8, 4))                  # peor en estimador pero no significativo → se etiqueta
    assert not P3.veredicto(t(-6, -12, -0.5), t(0, -5, 5))           # P(top 6) significativamente peor
    assert not P3.veredicto(t(1, -4, 6), t(-9, -15, -1))             # P(sobrevivir) significativamente peor
