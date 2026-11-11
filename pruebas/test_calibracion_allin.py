"""Calibración de los all-in (§1.9 R_paga, §2.8): shrinkage hacia lo actual, corte del rango de quien empuja y c de pago."""

import random

import pytest

import cartas as C
import poblacion as POB
import rangos as R
from capa1 import Capa1
from params import cargar_params
from test_capa1 import MesaFalsa, decidir, params as params_capa1, spot


def vacia_post():
    return {"faced": {c: [0, 0] for c in (R.FUERTE, R.MEDIA, R.PROYECTO, R.AIRE)},
            "libre": {c: [0, 0] for c in (R.FUERTE, R.MEDIA, R.PROYECTO, R.AIRE)}}


def datos(paga_pre=(0, 0), paga_post=(0, 0), emp_pre=(0, None), post=None):
    return {"paga": {"pre": list(paga_pre), "post": list(paga_post)},
            "empuja_pre": {"n": emp_pre[0], "q90": emp_pre[1], "q75": None, "q50": None},
            "empuja_post": post or vacia_post()}


def con_calibracion(**fuentes):
    p = params_capa1()
    p["calibracion_allin"] = {"activa": True, "s": 20.0, "bots": fuentes.get("bots", {}), "grupos": fuentes.get("grupos", {})}
    return p


# --- Shrinkage -----------------------------------------------------------------------------------------

def test_mezcla_con_prior_sin_datos_es_lo_actual_y_con_muchos_datos_es_lo_medido():
    assert POB.mezcla_con_prior(0.3, [(1.0, 0, 0)], 20.0) == pytest.approx(0.3)
    assert POB.mezcla_con_prior(0.3, [(1.0, 100_000, 0)], 20.0) == pytest.approx(0.0, abs=1e-3)
    assert POB.mezcla_con_prior(0.3, [(1.0, 20, 0)], 20.0) == pytest.approx(0.15)          # n = s: a mitad de camino
    # lo que π reparte entre tipos sin datos se queda en lo actual
    assert POB.mezcla_con_prior(0.3, [(0.5, 100_000, 0)], 20.0) == pytest.approx(0.15, abs=1e-3)


def test_c_calibrada_bot_reconocido_usa_sus_datos_y_si_no_los_grupos_por_pi():
    p = con_calibracion(bots={"bandido": datos(paga_pre=(1000, 0))},
                        grupos={"tag": datos(paga_pre=(1000, 200)), "station": datos(paga_pre=(1000, 0))})
    assert POB.c_calibrada(0.3, True, "bandido", {"tag": 1.0}, p) < 0.01                    # nunca paga: c → 0
    c_tag = POB.c_calibrada(0.3, True, None, {"tag": 1.0}, p)
    assert c_tag == pytest.approx((200 + 20 * 0.3) / 1020)
    c_mix = POB.c_calibrada(0.3, True, None, {"tag": 0.5, "station": 0.5}, p)
    assert c_mix == pytest.approx(0.5 * (200 + 6) / 1020 + 0.5 * 6 / 1020)
    # preflop y postflop son aparte
    assert POB.c_calibrada(0.3, False, "bandido", {"tag": 1.0}, p) == pytest.approx(0.3)   # sin datos postflop: lo actual


def test_c_calibrada_tipos_sin_datos_no_se_tocan():
    p = con_calibracion(grupos={"tag": datos(paga_pre=(1000, 0))})
    assert POB.c_calibrada(0.4, True, None, {"nit": 1.0}, p) == pytest.approx(0.4)
    assert POB.c_calibrada(0.4, True, None, {"maniaco": 1.0}, p) == pytest.approx(0.4)


def test_calibracion_activa_solo_con_el_interruptor_y_en_modo_profundo():
    p = con_calibracion()
    assert POB.calibracion_activa(p, True) and not POB.calibracion_activa(p, False)
    p["calibracion_allin"]["activa"] = False
    assert not POB.calibracion_activa(p, True)


# --- Rango de quien empuja ------------------------------------------------------------------------------

def test_corte_empuje_preflop_se_encoge_hacia_100():
    p = con_calibracion(bots={"base": datos(emp_pre=(200, 6.0))}, grupos={"tag": datos(emp_pre=(0, None))})
    t = POB.corte_empuje_preflop("base", {"tag": 1.0}, p)
    assert t == pytest.approx((200 * 6.0 + 20 * 100.0) / 220)
    assert POB.corte_empuje_preflop(None, {"tag": 1.0}, p) == pytest.approx(100.0)          # sin datos: sin recorte


def test_recortar_a_top_deja_solo_las_clases_del_top():
    r = R.rango_top(30)
    r2 = POB.recortar_a_top(r, 5.0)
    assert 0 < len(r2) < len(r)
    assert {R.clase_de_combo(*c) for c in r2.combos} <= set(R.clases_top(5.0))
    assert POB.recortar_a_top(r, 100.0) is r                                               # sin recorte
    vacio_resultado = POB.recortar_a_top(R.rango_de_clases(["72o"]), 5.0)                  # nada dentro del top: se conserva
    assert len(vacio_resultado) == len(R.rango_de_clases(["72o"]))


def _eventos_allin_preflop():
    return [("r0", "preflop", "allin", False)]


def test_rango_de_quien_empuja_preflop_se_recorta_solo_con_calibracion_y_en_profundo():
    mano = C.cartas_de_texto("7h 2c")
    cache = POB.CacheCategorias()
    pos = "CO"
    base = cargar_params()
    p = con_calibracion(bots={"base": datos(emp_pre=(500, 4.0))})
    sin = POB.rango_de_rival("r0", pos, _eventos_allin_preflop(), [], mano, base, cache,
                             expl={"bot": "base"}, profundo=True)
    con = POB.rango_de_rival("r0", pos, _eventos_allin_preflop(), [], mano, p, cache, expl={"bot": "base"}, profundo=True)
    no_prof = POB.rango_de_rival("r0", pos, _eventos_allin_preflop(), [], mano, p, cache, expl={"bot": "base"}, profundo=False)
    assert len(con) < len(sin)
    assert len(no_prof) == len(sin)                                                        # fuera de modo profundo no rige


def test_tabla_empuje_postflop_cambia_la_verosimilitud_por_categoria():
    post = vacia_post()
    post["faced"][R.FUERTE] = [200, 60]        # con mano fuerte empuja el 30 %
    post["faced"][R.AIRE] = [800, 4]           # con aire casi nunca
    p = con_calibracion(bots={"espia": datos(post=post)})
    tabla0 = {R.FUERTE: 0.34, R.MEDIA: 0.2, R.PROYECTO: 0.3, R.AIRE: 0.05}
    t = POB.tabla_empuje_postflop(tabla0, True, "espia", {"tag": 1.0}, p)
    assert t[R.FUERTE] == pytest.approx((60 + 20 * 0.34) / 220)
    assert t[R.AIRE] == pytest.approx((4 + 20 * 0.05) / 820)
    assert t[R.MEDIA] == pytest.approx(0.2)                                                # sin datos: lo actual
    assert t[R.FUERTE] / t[R.AIRE] > tabla0[R.FUERTE] / tabla0[R.AIRE]                    # el empuje es más informativo


# --- En la decisión --------------------------------------------------------------------------------------------

def _spot_subida():
    """Un rival subió a 3 bb preflop a 100 bb de stack: Bender decide con el menú completo (no es una apertura)."""
    historial = [{"id_jugador": "r0", "etapa": "preflop", "accion": {"tipo": "raise"}}]
    return spot("Ac Ts", rivales=((9700, 300),), yo=(9900, 100), pozo=400, apuesta_actual=300, historial=historial, boton=1)


def test_all_in_contra_quien_nunca_paga_tiene_c_casi_cero_con_la_calibracion():
    """Un rival que nunca paga un all-in preflop (como bandido en el historial): con la calibración c → 0 y f → 1."""
    turno = _spot_subida()
    p0 = params_capa1()
    p1 = con_calibracion(grupos={"tag": datos(paga_pre=(2000, 0))})
    _, _, i0 = decidir(turno, p0)
    _, _, i1 = decidir(turno, p1)
    fila0 = next(f for f in i0["tabla_ev"] if f["accion"] == "all-in")
    fila1 = next(f for f in i1["tabla_ev"] if f["accion"] == "all-in")
    assert fila1["c"]["r0"] < 0.01 < fila0["c"]["r0"]
    assert fila1["f"] > 0.98 and fila1["ev"] > fila0["ev"]
    # y no toca las apuestas que no son all-in
    x1 = next(f for f in i1["tabla_ev"] if f["accion"] == "x=1.0")
    x0 = next(f for f in i0["tabla_ev"] if f["accion"] == "x=1.0")
    assert x1["c"]["r0"] == pytest.approx(x0["c"]["r0"])


def test_la_calibracion_no_cambia_nada_si_esta_apagada_ni_en_modo_push_fold():
    turno = _spot_subida()
    p_off = con_calibracion(grupos={"tag": datos(paga_pre=(2000, 0))})
    p_off["calibracion_allin"]["activa"] = False
    p_ref = params_capa1()
    assert decidir(turno, p_off)[2]["tabla_ev"] == decidir(turno, p_ref)[2]["tabla_ev"]
    # stack corto (10 bb): push/fold, con c = 0,385 de Nash aunque la calibración diga otra cosa
    corto = spot("Ah Td", rivales=((900, 100),), yo=(950, 50), pozo=150, apuesta_actual=100, boton=0)
    p_on = con_calibracion(grupos={"tag": datos(paga_pre=(2000, 0))})
    fila = next(f for f in decidir(corto, p_on)[2]["tabla_ev"] if f["accion"] == "all-in")
    assert fila["c"]["r0"] == pytest.approx(0.385)
