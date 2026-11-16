"""Regla de elección de la versión final (decidir_final.py): márgenes, desempates y combinación."""

from decidir_final import decidir, gana, no_pierde


def t(m, lo, hi):
    return (m / 100, lo / 100, hi / 100)


def res(**c):
    base = {"base": {"fp": 40.0}}
    base.update(c)
    return base


def test_no_pierde_exige_estimador_mayor_o_igual_a_menos_2_y_limite_inferior_mayor_o_igual_a_menos_8():
    assert no_pierde(t(-2.0, -8.0, 4.0)) and no_pierde(t(0.0, -5.0, 5.0))
    assert not no_pierde(t(-2.1, -3.0, 1.0))            # el estimador baja de −2
    assert not no_pierde(t(0.0, -8.1, 8.0))             # el límite inferior baja de −8
    assert not no_pierde(None)


def test_gana_es_que_el_ic_excluya_el_cero_a_favor():
    assert gana(t(5.0, 0.1, 9.0)) and not gana(t(5.0, 0.0, 9.0)) and not gana(t(5.0, -1.0, 9.0))


def test_si_no_pasa_nada_la_final_es_la_base():
    v, _ = decidir(res(huella={"ent": t(-3.0, -9.0, 1.0), "desc": t(1.0, -5.0, 7.0), "fp": 10.0},
                       k6k={"ent": t(0.7, -5.1, 6.2), "desc": t(2.0, -4.0, 8.0), "fp": 40.0}))
    assert v == "base"


def test_un_arreglo_pasa_si_no_pierde_en_ambos_campos_y_baja_los_falsos_positivos():
    ok = {"ent": t(-1.0, -6.0, 4.0), "desc": t(0.5, -6.0, 7.0), "fp": 8.0}
    assert decidir(res(huella=ok))[0] == "huella"
    assert decidir(res(huella={**ok, "fp": 40.0}))[0] == "base"           # los falsos positivos NO bajan: no se adopta
    assert decidir(res(huella={**ok, "desc": t(-3.0, -9.0, 2.0)}))[0] == "base"


def test_sin_contra_no_necesita_que_baje_la_tasa_de_falsos_positivos():
    sc = {"ent": t(0.0, -5.0, 5.0), "desc": t(1.0, -4.0, 6.0), "fp": 40.0}
    assert decidir(res(sin_contra=sc))[0] == "sin_contra"


def test_si_pasan_los_dos_arreglos_elige_huella():
    ok = {"ent": t(0.0, -5.0, 5.0), "desc": t(1.0, -4.0, 6.0), "fp": 5.0}
    assert decidir(res(huella=ok, sin_contra={**ok, "fp": 40.0}))[0] == "huella"


def test_un_parametro_pasa_solo_si_gana_en_desconocido_y_no_pierde_en_entrenamiento():
    ok = {"ent": t(0.7, -5.1, 6.2), "desc": t(14.0, 2.0, 26.0), "fp": 40.0}
    assert decidir(res(c05=ok))[0] == "c05"
    assert decidir(res(c05={**ok, "desc": t(6.0, -6.0, 18.0)}))[0] == "base"        # no gana con IC que excluya el 0
    assert decidir(res(c05={**ok, "ent": t(-3.0, -9.0, 2.0)}))[0] == "base"          # pierde en entrenamiento


def test_si_pasan_k6k_y_c05_elige_k6k_por_ser_mas_simple():
    ok = {"ent": t(0.7, -5.1, 6.2), "desc": t(14.0, 2.0, 26.0), "fp": 40.0}
    assert decidir(res(c05=ok, k6k=ok))[0] == "k6k"


def test_si_pasan_un_arreglo_y_un_parametro_se_pide_la_combinacion():
    arreglo = {"ent": t(0.0, -5.0, 5.0), "desc": t(1.0, -4.0, 6.0), "fp": 5.0}
    param = {"ent": t(0.7, -5.1, 6.2), "desc": t(14.0, 2.0, 26.0), "fp": 40.0}
    v, _ = decidir(res(huella=arreglo, c05=param))
    assert v == ("f", "huella", "c05")
    v, _ = decidir(res(huella=arreglo, c05=param, k6k=param))
    assert v == ("f", "huella", "k6k")
