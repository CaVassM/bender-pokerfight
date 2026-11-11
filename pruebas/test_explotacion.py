"""Pruebas del paso 5: ρ y θ (§3.2, §3.3), ajustes por tipo y bot reconocido (§3.4), Chen de `base`."""

import random

import pytest

import cartas as C
import explotacion as EXP
import poblacion as POB
import rangos as R
from capa1 import Capa1
from params import cargar_params
from rivales import Beta, Memoria, Rival
from test_capa1 import MesaFalsa, spot

P = cargar_params()
CFG = P["explotacion"]


def beta_con(k, n, m=0.3, s=20):
    b = Beta(m, s)
    for i in range(n):
        b.observar(i < k, 1.0)                    # λ = 1: Bayes puro, como en los ejemplos del .tex
    return b


# --- §3.2 ρ ------------------------------------------------------------------------------------------

def test_rho_ejemplos_del_tex():
    # VPIP, m = 0,30. 10 manos (p̂ = 0,433, σ = 0,089): ρ = 0,8·(1 − 0,089/0,133) = 0,26
    b10 = beta_con(7, 10)
    assert b10.p == pytest.approx(0.433, abs=0.001) and b10.sigma == pytest.approx(0.089, abs=0.001)
    assert EXP.rho_de(b10, 0.30, CFG) == pytest.approx(0.26, abs=0.01)
    # 85 manos (p̂ = 0,552, σ = 0,048): ρ = 0,65
    b85 = beta_con(52, 85)
    assert b85.p == pytest.approx(0.552, abs=0.001)
    assert EXP.rho_de(b85, 0.30, CFG) == pytest.approx(0.65, abs=0.01)


def test_rho_es_cero_con_pocas_observaciones_o_sin_desvio():
    assert EXP.rho_de(beta_con(7, 7), 0.30, CFG) == 0.0                 # n = 7 < n_min = 8
    assert EXP.rho_de(beta_con(0, 0), 0.30, CFG) == 0.0                 # p̂ = m
    b = beta_con(3, 10)                                                 # p̂ = 0,333, muy cerca de m = 0,30
    assert EXP.rho_de(b, 0.30, CFG) == 0.0                              # la diferencia es menor que κσ
    assert EXP.rho_de(beta_con(100, 100), 0.30, {**CFG, "rho_max": 0.0}) == 0.0


def test_rho_sube_con_los_datos_y_no_pasa_de_rho_max():
    rhos = [EXP.rho_de(beta_con(int(0.7 * n), n), 0.30, CFG) for n in (10, 30, 100, 400)]
    assert rhos == sorted(rhos) and rhos[-1] <= CFG["rho_max"] + 1e-9 and rhos[-1] > 0.7


# --- §3.3 θ --------------------------------------------------------------------------------------------

def test_theta_mezcla_lineal():
    assert EXP.theta(0.4, 0.8, 0.0) == 0.4 and EXP.theta(0.4, 0.8, 1.0) == 0.8
    assert EXP.theta(0.4, 0.8, 0.25) == pytest.approx(0.5)


def lectura_con(sigue_chica=(0.9, 0.5), sigue_grande=(0.3, 0.5)):
    lec = EXP.Lectura("r0")
    lec.stats = {"sigue_chica": {"p": sigue_chica[0], "sigma": 0.05, "n": 50, "rho": sigue_chica[1]},
                 "sigue_grande": {"p": sigue_grande[0], "sigma": 0.05, "n": 50, "rho": sigue_grande[1]},
                 "vpip": {"p": 0.3, "sigma": 0.05, "n": 50, "rho": 0.0}, "pfr": {"p": 0.1, "sigma": 0.05, "n": 50, "rho": 0.0}}
    return lec


def test_c_mezclada_usa_la_caja_chica_o_la_grande_segun_el_tamano():
    lec = lectura_con()
    assert EXP.c_mezclada(0.5, lec, 0.5, P) == pytest.approx(0.7)      # chica (x <= 0,6): 0,5·0,5 + 0,5·0,9
    assert EXP.c_mezclada(0.5, lec, 1.5, P) == pytest.approx(0.4)      # grande: 0,5·0,5 + 0,5·0,3
    assert EXP.c_mezclada(0.5, lectura_con(sigue_chica=(0.9, 0.0)), 0.5, P) == 0.5   # ρ = 0: no se mueve


# --- §3.4 tipos y bots -------------------------------------------------------------------------------------

def rival_con(huella_cajas=(), log_pi=None, tmp=None):
    r = Rival("r0", P)
    for caja in huella_cajas:
        r.obs_huella(caja)
    if log_pi:
        r.log_pi.update(log_pi)
    return r


def test_lectura_reconoce_tipo_dominante_y_bot():
    r = rival_con(huella_cajas=[1] * 6 + [5, 1, 1, 1])                 # montos de "base" (calibrados)
    lec = EXP.lectura_de(r, P)
    assert lec.bot == "base" and lec.bot_p >= 0.9
    r2 = rival_con(log_pi={"station": 0.0, "tag": -5.0, "nit": -5.0, "maniaco": -5.0, "aleatorio": -5.0})
    assert EXP.lectura_de(r2, P).tipo == "station"
    assert EXP.lectura_de(rival_con(), P).tipo is None                   # sin datos, ningún tipo llega a τ = 0,7
    assert EXP.lectura_de(r, P, usar_bots=False).bot is None


def test_sin_farol_solo_si_todos_son_de_esos_tipos():
    a, b = EXP.Lectura("a"), EXP.Lectura("b")
    a.tipo, b.tipo = "station", "maniaco"
    assert EXP.sin_farol([a, b]) is not None
    b.tipo = "tag"
    assert EXP.sin_farol([a, b]) is None
    assert EXP.sin_farol([]) is None


# --- Chen y el rango exacto de base ------------------------------------------------------------------------------

def test_chen_port_del_codigo_de_base():
    def ch(t):
        return POB.chen(tuple(sorted(C.cartas_de_texto(t))))
    assert ch("AsAh") == 20 and ch("AsKs") == 12 and ch("AsKh") == 10
    assert ch("Ts9s") == 8 and ch("JsTs") == 9                          # conectora baja suited: +1
    assert ch("7s2h") == pytest.approx(-1.5)
    assert ch("2s2h") == 5                                              # pareja mínima: 5


def test_rango_de_chen_de_base():
    sube, paga = POB.rango_de_chen(9.0), POB.rango_de_chen(5.0, 9.0)
    assert 80 <= len(sube) <= 200 and 250 <= len(paga) <= 600           # ~6-14 % y ~20-45 % de los 1326 combos
    assert not (set(sube.combos) & set(paga.combos))
    assert "AA" in sube.conteo_por_clase() and "AKo" in sube.conteo_por_clase()
    assert "72o" not in sube.conteo_por_clase() and "72o" not in paga.conteo_por_clase()


def test_plantilla_por_bot_reemplaza_a_la_mezcla():
    mezcla = POB.plantilla_mezcla(P["prior_tipos"], P)
    base = POB.plantilla_mezcla(P["prior_tipos"], P, bot="base")
    assert base == {c: tuple(P["plantillas_bot"]["base"][c]) for c in base}
    assert base != mezcla
    assert POB.prob_apuesta({"tag": 1.0}, P, bot="base")["media"] > 0.9    # base apuesta con cualquier pareja
    assert POB.plantilla_mezcla({"tag": 1.0}, P, bot="no_existe") == POB.plantilla_mezcla({"tag": 1.0}, P)


def test_rango_preflop_mezcla_con_lo_medido_segun_rho():
    base = POB.rango_preflop(1, 0, "UTG", P)
    sin_rho = POB.rango_preflop(1, 0, "UTG", P, {"vpip": (0.3, 0.0), "pfr": (0.5, 0.0), "bot": None})
    con_rho = POB.rango_preflop(1, 0, "UTG", P, {"vpip": (0.3, 0.0), "pfr": (0.5, 0.8), "bot": None})
    assert len(sin_rho) == len(base)                                    # ρ = 0: igual que la población
    assert len(con_rho) > 2 * len(base)                                 # PFR medido de 50 % con ρ = 0,8: rango ancho


# --- Integración con la Capa 1 ------------------------------------------------------------------------------------

def capa_con_memoria(params, rival_huella=(), semilla=3):
    mem = Memoria(params, persistir=False)
    r = mem.rival("r0")
    for caja in rival_huella:
        r.obs_huella(caja)
    return Capa1(params, rng=random.Random(semilla), memoria=mem)


def spot_preflop_con_subida():
    hist = [{"id_jugador": "r0", "etapa": "preflop", "accion": {"tipo": "raise"}}]
    return spot("As Kh", rivales=((9700, 300),), yo=(9900, 100), pozo=400, apuesta_actual=300, historial=hist, boton=1)


def test_el_bot_base_reconocido_juega_con_el_rango_de_chen():
    p = cargar_params()
    p["reloj"].update({"n_min": 300, "eps_obj": 0.02})
    capa = capa_con_memoria(p, rival_huella=[1] * 8)
    _, _, info = capa.decidir(spot_preflop_con_subida(), MesaFalsa())
    ex = info["rivales"]["r0"]["explotacion"]
    assert ex["bot"] == "base"
    vivos = len(POB.rango_de_chen(9.0).filtrar(C.mascara(C.cartas_de_texto("As Kh"))))
    assert info["rangos"]["r0"]["combos"] == vivos                      # su rango es exactamente Chen >= 9 sin las cartas muertas


def test_sin_explotacion_no_hay_lectura_ni_bot():
    p = cargar_params()
    p["explotacion"]["activa"] = False
    p["reloj"].update({"n_min": 300, "eps_obj": 0.02})
    capa = capa_con_memoria(p, rival_huella=[1] * 8)
    _, _, info = capa.decidir(spot_preflop_con_subida(), MesaFalsa())
    assert "explotacion" not in info["rivales"]["r0"]
    assert info["rangos"]["r0"]["combos"] != len(POB.rango_de_chen(9.0).filtrar(C.mascara(C.cartas_de_texto("As Kh"))))


def test_con_station_dominante_se_descartan_los_faroles():
    p = cargar_params()
    p["explotacion"]["filtros_tipo"] = True               # apagado por defecto: aquí se prueba la regla del .tex
    p["reloj"].update({"n_min": 300, "eps_obj": 0.02})
    capa = capa_con_memoria(p)
    capa.memoria.rival("r0").log_pi.update({"station": 0.0, "tag": -6.0, "nit": -6.0, "maniaco": -6.0, "aleatorio": -6.0})
    turno = spot("7h 6h", "Ks 9d 2c", rivales=((9000, 0),), yo=(9000, 0), pozo=600)
    _, _, info = capa.decidir(turno, MesaFalsa())
    apuestas = [f for f in info["tabla_ev"] if f["tipo"] in ("bet", "allin")]
    assert apuestas and all(f["descartada"] for f in apuestas)
    assert any("no se farolea" in f["descartada"] for f in apuestas) or all("variante" in f["descartada"] or "multiway" in f["descartada"] for f in apuestas)
