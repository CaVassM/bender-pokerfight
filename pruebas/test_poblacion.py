"""Pruebas del modelo de población (poblacion.py): c(x), plantillas, rangos preflop,
reajuste por acciones y el ejemplo numérico de §2.1."""

import pytest

import cartas as C
import poblacion as POB
import rangos as R
from estado import Jugador
from params import cargar_params

P = cargar_params()


def cs(t):
    return C.cartas_de_texto(t)


# --- §1.7 c(x) -----------------------------------------------------------------------------

def test_c_de_poblacion_ejemplos_del_tex():
    assert [round(POB.c_poblacion(x, False, P["pob"]), 2) for x in (0.5, 1, 2)] == [0.51, 0.42, 0.31]
    assert abs(POB.c_poblacion(0.5, True, P["pob"]) - (0.5098 + 0.12)) < 1e-3
    assert POB.c_poblacion(0.0, True, P["pob"]) == pytest.approx(0.77)          # 0,65 + 0,12 (sin llegar al tope)
    assert POB.c_poblacion(0.0, True, {**P["pob"], "a": 0.95}) == 0.9            # el tope de 0,9 recorta
    # f = Π(1 − c_i) con c = 0,45 y 0,60
    assert abs((1 - 0.45) * (1 - 0.60) - 0.22) < 1e-9


# --- §2.2 plantillas ------------------------------------------------------------------------

def test_plantilla_promedio_y_sigue():
    pl = POB.plantilla_mezcla({"tag": 1.0}, P)
    sigue = {cat: round(v[1] + v[2], 2) for cat, v in pl.items()}
    assert sigue == {"fuerte": 0.95, "media": 0.65, "proyecto": 0.75, "aire": 0.15}
    for v in pl.values():
        assert abs(sum(v) - 1.0) < 1e-9                                        # cada fila es una distribución
    mezcla = POB.plantilla_mezcla(P["prior_tipos"], P)
    for v in mezcla.values():
        assert abs(sum(v) - 1.0) < 1e-9


def test_prob_apuesta_por_tipo():
    pa = POB.prob_apuesta({"tag": 1.0}, P)
    assert pa == {"fuerte": 0.65, "media": 0.35, "proyecto": 0.45, "aire": 0.25}
    assert POB.prob_apuesta({"nit": 1.0}, P)["fuerte"] == pytest.approx(0.455)
    assert POB.prob_apuesta({"maniaco": 1.0}, P)["fuerte"] == 0.95            # tope .95
    assert POB.prob_apuesta({"aleatorio": 1.0}, P)["aire"] == 0.5


# --- §2.1 el ejemplo del .tex: J♦7♣2♠, héroe A♠J♥, rival con el top 25 % ------------------------

def ejemplo():
    mano, board = cs("As Jh"), cs("Jd 7c 2s")
    rango = R.rango_de_clases(R.clases_top(25), C.mascara(mano + board))
    cache = POB.CacheCategorias()
    por_cat = {}
    for combo in rango.combos:
        k = R.categoria_mano(combo, board)
        por_cat[k] = por_cat.get(k, 0) + 1
    return mano, board, rango, cache, por_cat


def test_ejemplo_2_1_combos_vivos_y_fuertes():
    _, _, rango, _, por_cat = ejemplo()
    assert abs(len(rango) - 259) <= 5                  # 259 combos vivos
    assert abs(por_cat.get("fuerte", 0) - 43) <= 5     # 43 fuertes
    assert por_cat.get("proyecto", 0) == 0             # 0 proyectos (board sin colores ni escaleras)


def test_ejemplo_2_1_c_cerca_de_0_37():
    _, board, rango, cache, _ = ejemplo()
    pl = POB.plantilla_mezcla({"tag": 1.0}, P)
    assert abs(POB.c_sigue(rango, board, pl, cache) - 0.37) <= 0.02
    # Con las cuentas exactas del .tex: (43·.95 + 45·.65 + 171·.15) / 259 = 0,37
    assert abs((43 * .95 + 45 * .65 + 171 * .15) / 259 - 0.37) < 0.001


def test_ejemplo_2_1_tras_pagar_el_aire_baja_del_66_al_19_por_ciento():
    mano, board, rango, cache, por_cat = ejemplo()
    antes = por_cat["aire"] / len(rango)
    assert abs(antes - 0.66) <= 0.04
    pl = POB.plantilla_mezcla({"tag": 1.0}, P)
    pago = POB.rango_de_pago(rango, board, pl, cache, 0.02)
    pesos = {}
    for combo, w in zip(pago.combos, pago.pesos):
        k = R.categoria_mano(combo, board)
        pesos[k] = pesos.get(k, 0.0) + w
    assert abs(pesos["aire"] / pago.total - 0.19) <= 0.03                      # 19 % en el .tex
    assert abs(pago.total - 1.0) < 1e-9


@pytest.mark.xfail(strict=True, reason=(
    "Con el ranking propio (decisión del usuario: se mantiene) el top 25 % trae 334 combos en vez de 340 y "
    "K7s, A2s y 44 entran al rango: salen 43 fuertes / 51 medios / 162 aire en vez de 43 / 45 / 171. "
    "Diferencia en media (6) y aire (9) por encima de ±5; ver reporte del paso 3."))
def test_ejemplo_2_1_medios_y_aire_dentro_de_5_combos():
    _, _, _, _, por_cat = ejemplo()
    assert abs(por_cat.get("media", 0) - 45) <= 5
    assert abs(por_cat.get("aire", 0) - 171) <= 5


# --- §2.8 rango preflop y re-subidas ---------------------------------------------------------------

def test_rango_preflop_segun_lo_que_hizo():
    abre_utg = POB.rango_preflop(1, 0, "UTG", P)
    abre_btn = POB.rango_preflop(1, 0, "BTN", P)
    reraise = POB.rango_preflop(2, 0, "UTG", P)
    assert len(abre_utg) < len(abre_btn) and len(reraise) < len(abre_utg)
    assert abs(len(abre_utg) / 1326 * 100 - 14.3) < 0.6
    assert len(POB.rango_preflop(0, 0, "BB", P)) == 1326                        # no hizo nada: mano al azar
    paga = POB.rango_preflop(0, 1, "CO", P)
    pesos = paga.peso_total_por_clase()
    assert pesos["AA"] == pytest.approx(6 * 0.3)                               # el top del PFR entra con peso 0,3
    solo_vpip = [c for c in R.clases_top(30) if c not in set(R.clases_top(25.5))][0]   # en el VPIP, fuera del PFR de CO
    assert pesos[solo_vpip] == pytest.approx(R.n_combos(solo_vpip) * 1.0)       # peso 1
    assert "32o" not in pesos


def test_top_fraccion_conserva_las_mejores_manos():
    r = R.rango_alazar()
    mitad = POB.top_fraccion(r, 0.5)
    assert abs(mitad.total - 0.5 * r.total) < 1e-6
    assert "AA" in mitad.conteo_por_clase() and "72o" not in mitad.conteo_por_clase()


# --- Rangos desde el historial ------------------------------------------------------------------------

def hist(*acciones):
    return [{"id_jugador": i, "etapa": e, "accion": {"tipo": t}} for i, e, t in acciones]


def test_eventos_marcan_si_enfrentaba_apuesta():
    ev = POB.eventos(hist(("a", "flop", "check"), ("b", "flop", "bet"), ("a", "flop", "call"), ("c", "turn", "check")))
    assert [e[3] for e in ev] == [False, False, True, False]


def test_el_rango_se_estrecha_con_las_acciones_postflop():
    mano, board = cs("As Kh"), cs("Jd 7c 2s")
    cache = POB.CacheCategorias()
    pos = "CO"
    sin = POB.rango_de_rival("r", pos, POB.eventos(hist(("r", "preflop", "raise"))), board, mano, P, cache)
    apuesta = POB.rango_de_rival("r", pos, POB.eventos(hist(("r", "preflop", "raise"), ("r", "flop", "bet"))), board, mano, P, cache)
    paso = POB.rango_de_rival("r", pos, POB.eventos(hist(("r", "preflop", "raise"), ("r", "flop", "check"))), board, mano, P, cache)

    def fuertes(r):
        s = sum(w for c, w in zip(r.combos, r.pesos) if R.categoria_mano(c, board) == R.FUERTE)
        return s / r.total
    assert fuertes(apuesta) > fuertes(sin) > fuertes(paso)                     # apostar sube la fuerza; pasar la baja
    assert not (set(C.cartas_de_texto("As Kh Jd 7c 2s")) & {x for c in sin.combos for x in c})   # sin cartas muertas
