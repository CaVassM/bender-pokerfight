"""Arreglo de las pruebas de estrés (Capa 3, paso 0b): S_ef con S0 (§1.4) y regla de compromiso solo en modo intermedio (§1.11).

Antes, con un rival all-in su saldo era 0, S_ef = 0, entraba push/fold y la regla de compromiso descartaba el call:
Bender se retiraba con AA contra un all-in de 100 bb (HU contra un bot que va all-in siempre: -147 bb/100).
"""

import pytest

from test_capa1 import decidir, params, spot


def _spot_allin_ajeno(mano, saldo_yo=9_950, apuesta_yo=50, total_rival=10_000):
    """Un rival fue all-in por `total_rival` fichas; yo tengo `saldo_yo` detrás y `apuesta_yo` puesto."""
    return spot(mano, rivales=((0, total_rival),), yo=(saldo_yo, apuesta_yo), pozo=total_rival + apuesta_yo,
                apuesta_actual=total_rival, boton=0)


def _p(utilidad=True):
    p = params(n_min=500, eps_obj=0.02)
    p["riesgo"]["utilidad"] = utilidad
    return p


@pytest.mark.parametrize("utilidad", [True, False])
def test_paga_un_all_in_de_100bb_con_manos_fuertes_y_se_retira_con_basura(utilidad):
    for mano in ("As Ah", "Kd Kc", "Ah Qd"):
        accion, _, info = decidir(_spot_allin_ajeno(mano), _p(utilidad))
        call = next(f for f in info["tabla_ev"] if f["tipo"] == "call")
        assert info["modo"] == "profundo" and info["s_ef_bb"] == 100.0
        assert call["ev"] > 0 and call["descartada"] is None, mano
        assert accion == {"tipo": "call"}, mano
    accion, _, info = decidir(_spot_allin_ajeno("7s 2c"), _p(utilidad))
    assert accion == {"tipo": "fold"} and next(f for f in info["tabla_ev"] if f["tipo"] == "call")["ev"] < 0


def test_el_modo_no_cambia_dentro_de_la_mano_por_un_all_in_ajeno():
    t_antes = spot("As Ah", rivales=((10_000, 0),), yo=(9_950, 50), pozo=150, apuesta_actual=100)
    t_despues = _spot_allin_ajeno("As Ah")
    assert decidir(t_antes)[2]["modo"] == decidir(t_despues)[2]["modo"] == "profundo"


def test_stack_corto_real_mantiene_push_fold_y_paga_el_all_in_con_aa():
    """10 bb al empezar la mano: push/fold. Igualar el all-in es la opción «all-in» y la regla de compromiso no rige."""
    accion, _, info = decidir(_spot_allin_ajeno("As Ah", saldo_yo=950, apuesta_yo=50, total_rival=1_000), _p())
    assert info["modo"] == "push_fold" and info["s_ef_bb"] == 10.0
    assert all(f["descartada"] is None for f in info["tabla_ev"])
    assert accion["tipo"] in ("call", "allin")
    accion, _, info = decidir(_spot_allin_ajeno("7s 2c", saldo_yo=950, apuesta_yo=50, total_rival=1_000), _p())
    assert info["modo"] == "push_fold" and accion == {"tipo": "fold"}


def test_compromiso_solo_en_modo_intermedio():
    """20 bb (intermedio): un call que cuesta más de 1/3 del stack se descarta. Con 40 bb (profundo) el mismo call no."""
    def llamada(saldo, rival_saldo, rival_apuesta):
        t = spot("As Kh", rivales=((rival_saldo, rival_apuesta),), yo=(saldo, 100), pozo=rival_apuesta + 150,
                 apuesta_actual=rival_apuesta, boton=0)
        return decidir(t, params(n_min=300, eps_obj=0.02))[2]
    info = llamada(1_900, 1_200, 800)                       # S0 = 2 000 = 20 bb; C = 700 > 2 000/3
    assert info["modo"] == "intermedio"
    assert next(f for f in info["tabla_ev"] if f["tipo"] == "call")["descartada"].startswith("compromiso")
    info = llamada(3_900, 3_200, 800)                       # 40 bb: profundo, sin compromiso
    assert info["modo"] == "profundo"
    assert next(f for f in info["tabla_ev"] if f["tipo"] == "call")["descartada"] is None


def test_en_intermedio_igualar_un_all_in_que_pone_todas_las_fichas_no_se_descarta():
    accion, _, info = decidir(_spot_allin_ajeno("As Ah", saldo_yo=1_900, apuesta_yo=100, total_rival=2_000), _p())
    assert info["modo"] == "intermedio"
    assert all(f["descartada"] is None for f in info["tabla_ev"] if f["tipo"] in ("call", "allin"))
    assert accion["tipo"] in ("call", "allin")


def test_multiway_cuenta_a_los_respondedores_no_a_los_all_in():
    """Con 3 rivales con fichas se descartan las apuestas sin valor; con 2 respondedores y 1 all-in, no."""
    def descartes(rivales):
        t = spot("7h 2c", "Ks Qd 4s", rivales=rivales, yo=(10_000, 0), pozo=900)
        return [f["descartada"] for f in decidir(t, params(n_min=300, eps_obj=0.02))[2]["tabla_ev"] if f["tipo"] in ("bet", "raise")]
    tres = descartes(((10_000, 0), (10_000, 0), (10_000, 0)))
    assert tres and all((d or "").startswith("multiway") for d in tres)
    dos_y_allin = descartes(((10_000, 0), (10_000, 0), (0, 0)))
    assert dos_y_allin and not any((d or "").startswith("multiway") for d in dos_y_allin)


def test_e_prima_incluye_el_rango_del_rival_all_in():
    t = spot("As Ah", "Ks Qd 4s", rivales=((10_000, 0), (0, 0)), yo=(10_000, 0), pozo=900)
    info = decidir(t, params(n_min=300, eps_obj=0.02))[2]
    assert info["equities_si_pagan"] and all(e["allin_en_el_bote"] == ["r1"] for e in info["equities_si_pagan"])
