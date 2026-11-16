"""Huella corregida (§2.7): mínimo de apuestas medidas (`huella.min_z`), umbral y evidencia del tamaño de la apertura preflop."""

import copy
import math

from params import cargar_params
from rivales import Memoria, Observador, Rival
from test_rivales import acc, estado, jug

CAJA_BASE = 1                      # z = 0,4: la caja donde `base` apuesta el 77 % de las veces (tabla calibrada)


def params(**huella):
    p = cargar_params()
    p["huella"].update(copy.deepcopy(huella))
    return p


def con_apertura(**cambios):
    p = cargar_params()
    p["huella"]["apertura_3bb"].update(cambios)
    p["huella"]["apertura_3bb"]["activa"] = True
    return p


def parecido_a_base(p, n_z):
    r = Rival("x", p)
    for _ in range(n_z):
        r.obs_huella(CAJA_BASE)
    return r


def test_por_defecto_la_huella_es_la_de_siempre():
    p = cargar_params()
    assert p["huella"]["min_z"] == 0 and p["huella"]["apertura_3bb"]["activa"] is False and p["huella"]["umbral"] == 0.9


def test_min_z_exige_apuestas_medidas_antes_de_reconocer():
    p = params(min_z=8)
    r = parecido_a_base(p, 6)
    assert r.huella()["base"] > 0.97 and r.bot_reconocido() is None            # P alta pero solo 6 apuestas medidas
    r.obs_huella(CAJA_BASE)
    r.obs_huella(CAJA_BASE)
    assert r.n_z == 8 and r.bot_reconocido()[0] == "base"
    assert parecido_a_base(cargar_params(), 3).bot_reconocido()[0] == "base"    # sin mínimo (por defecto) reconoce antes


def test_el_umbral_se_aplica_a_la_probabilidad():
    r = Rival("x", cargar_params())
    r.log_huella = {b: -50.0 for b in r.log_huella}
    r.log_huella["propio"], r.log_huella["base"] = math.log(0.05), math.log(0.95)
    assert r.bot_reconocido()[0] == "base"                                      # 0,95 >= 0,9
    p97 = params(umbral=0.97)
    r97 = Rival("y", p97)
    r97.log_huella = dict(r.log_huella)
    assert r97.bot_reconocido() is None                                         # 0,95 < 0,97


def test_una_apertura_a_2_5_bb_descarta_a_los_bots_que_abren_siempre_a_3_bb():
    p = con_apertura()
    r = parecido_a_base(p, 10)                                                  # postflop idéntico a `base`
    assert r.bot_reconocido()[0] == "base"                                      # sin la evidencia de apertura: falso positivo
    antes = r.huella()["base"]
    r.obs_apertura(2.5)                                                         # una apertura a 2,5 bb (como Bender) ya frena...
    assert r.huella()["base"] < antes
    for _ in range(5):
        r.obs_apertura(2.5)                                                     # ...y con seis (Bender abre ~1 de cada 5 manos), ninguno sobrevive
    post = r.huella()
    assert post["base"] < 0.01 and post["espia"] < 0.01 and post["bandido"] < 0.01
    assert r.bot_reconocido() is None
    assert r.contadores["aperturas"] == {"n": 6, "tam_exacto": 0}


def test_abrir_siempre_a_3_bb_refuerza_a_base_y_castiga_a_estadistico_y_aleatorio():
    p = con_apertura()
    r = Rival("x", p)
    antes = r.huella()
    for _ in range(5):
        r.obs_apertura(3.0)
    despues = r.huella()
    assert despues["base"] / despues["propio"] > antes["base"] / antes["propio"] * 2        # sube frente a «propio»
    assert despues["estadistico"] < antes["estadistico"] / 10 and despues["aleatorio"] < antes["aleatorio"] / 10
    assert r.contadores["aperturas"]["tam_exacto"] == 5


def test_el_observador_mide_la_primera_subida_preflop_en_bb_y_solo_si_esta_activo(tmp_path):
    for activa, esperado in ((False, None), (True, 1)):
        p = con_apertura() if activa else cargar_params()
        mem = Memoria(p, str(tmp_path / f"m{activa}"), persistir=False)
        obs = Observador(p, mem, mi_id="yo")
        base = [jug("yo", 0, 10_000), jug("a", 1, 9_950, 50), jug("b", 2, 9_900, 100)]
        obs.al_mensaje({"tipo": "mano_inicio", "cartas": [], "estado": estado("m1", "preflop", 150, 100, base, [])})
        h = [acc("yo", "preflop", "fold"), acc("a", "preflop", "raise", 300)]
        ahora = [jug("yo", 0, 10_000), jug("a", 1, 9_700, 300), jug("b", 2, 9_900, 100)]
        obs.al_mensaje({"tipo": "estado", "estado": estado("m1", "preflop", 400, 300, ahora, h)})
        ap = mem.rival("a").contadores.get("aperturas")
        assert (ap["n"] if ap else None) == esperado
        if ap:
            assert ap["tam_exacto"] == 1                                         # 300 / 100 = 3,0 bb exactos
        # la re-subida de b (a 9 bb) ya no es una apertura
        h2 = h + [acc("b", "preflop", "raise", 900)]
        obs.al_mensaje({"tipo": "estado", "estado": estado("m1", "preflop", 1300, 900, ahora, h2)})
        assert mem.rival("b").contadores.get("aperturas") is None
