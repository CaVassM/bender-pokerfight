"""final2_eval.py: configuraciones válidas, semillas nuevas y regla de no inferioridad (C > B > A)."""

import json

import final2_eval as F2
from params import _mezclar, cargar_params


def t(m, lo, hi):
    return (m / 100, lo / 100, hi / 100)


def par(top6, surv=(0.0, -5.0, 5.0)):
    return {"top6": t(*top6), "surv": t(*surv)}


def res(b_desc, b_ent, c_desc, c_ent, cb_desc=(0.0, -5.0, 5.0), cb_ent=(0.0, -5.0, 5.0), **sv):
    return {"B": {"vsA": {"desc": par(b_desc, sv.get("b_sd", (0.0, -5.0, 5.0))), "ent": par(b_ent)}},
            "C": {"vsA": {"desc": par(c_desc), "ent": par(c_ent, sv.get("c_se", (0.0, -5.0, 5.0)))},
                  "vsB": {"desc": par(cb_desc, sv.get("cb_sd", (0.0, -5.0, 5.0))), "ent": par(cb_ent)}}}


def test_configuraciones_validas_y_c_es_k6k_mas_huella():
    for cid, cfg in F2.configuraciones().items():
        p = cargar_params()
        _mezclar(p, json.loads(json.dumps(cfg["variante"])))
        assert cfg["id"] == cid
    p = cargar_params()
    _mezclar(p, F2.configuraciones()["k6k_huella"]["variante"])
    assert p["riesgo"]["K"] == 6000 and p["huella"]["min_z"] == 8 and p["huella"]["umbral"] == 0.97 and p["huella"]["apertura_3bb"]["activa"]
    assert F2.configuraciones()["k6k"]["variante"]["riesgo"]["K"] == 6000


def test_las_semillas_son_nuevas():
    import bandido_eval as BE
    import confirmacion as CONF
    import final_eval as FE
    import halving as H
    usadas = [H.SEMILLA_RONDAS, H.SEMILLA_VALID, CONF.SEMILLA_NUEVA, BE.SEMILLA_DESC, 12_000_000, FE.SEMILLA_DESC]
    for s0 in (F2.SEMILLA_DESC, F2.SEMILLA_ENT):
        assert all(abs(s0 - u) >= 1_000_000 for u in usadas)                      # 300 << 1 000 000: no se pisan los bloques


def test_si_todo_cumple_gana_c_la_mas_completa():
    assert F2.decidir(res((4, 0, 8), (3, 0, 6), (5, 0, 9), (2, 0, 5)))[0] == "C"


def test_si_c_es_significativamente_peor_que_b_se_elige_b():
    r = res((4, 0, 8), (3, 0, 6), (5, 0, 9), (2, 0, 5), cb_ent=(-6.0, -10.0, -1.0))
    assert F2.decidir(r)[0] == "B"


def test_promedio_negativo_de_los_dos_campos_descarta():
    assert F2.decidir(res((-3, -9, 3), (1, -5, 6), (-3, -9, 3), (1, -5, 6)))[0] == "A"        # promedio −1 pt
    assert F2.decidir(res((-3, -9, 3), (3, -3, 9), (-3, -9, 3), (3, -3, 9)))[0] == "C"        # promedio 0 pt: cumple (≥ 0)


def test_un_delta_de_supervivencia_significativamente_negativo_descarta_esa_config():
    r = res((4, 0, 8), (3, 0, 6), (5, 0, 9), (2, 0, 5), b_sd=(-6.0, -11.0, -1.0), c_se=(0.0, -5.0, 5.0))
    assert F2.decidir(r)[0] == "C"                                                          # B queda fuera, C cumple
    r = res((4, 0, 8), (3, 0, 6), (5, 0, 9), (2, 0, 5), b_sd=(-6.0, -11.0, -1.0), c_se=(-6.0, -11.0, -1.0))
    assert F2.decidir(r)[0] == "A"


def test_no_significativo_es_cumple_aunque_el_estimador_de_supervivencia_sea_negativo():
    r = res((4, 0, 8), (3, 0, 6), (5, 0, 9), (2, 0, 5), b_sd=(-4.0, -9.0, 1.0))
    assert F2.decidir(r)[0] == "C"
