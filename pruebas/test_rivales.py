"""Pruebas de la Capa 2 (rivales.py): Beta con olvido, huella de montos, observador de mensajes,
tipo con cartas mostradas y persistencia."""

import math

import pytest

import cartas as C
from params import cargar_params
from rivales import Beta, Memoria, Observador, Rival, caja_de_z, posterior_huella

P = cargar_params()

# La tabla provisional del .tex (§2.7): los tests de la huella usan ESTA tabla, no la calibrada.
TABLA_TEX = {
    "base": [.01, .40, .01, .01, .01, .52, .01, .01, .02],
    "novato": [.20, .01, .44, .01, .01, .29, .01, .01, .02],
    "espia": [.01, .01, .44, .24, .01, .01, .14, .12, .02],
    "bandido": [.01, .01, .44, .01, .29, .01, .01, .20, .02],
    "estadistico": [.01, .01, .30, .08, .08, .08, .08, .08, .28],
    "propio": [1 / 9] * 9,
}
HUELLA_TEX = {"cajas": [0.33, 0.4, 0.5, 0.6, 0.66, 0.75, 0.9, 1.0], "tolerancia": 0.03, "umbral": 0.9, "tabla": TABLA_TEX,
              "prior": {"propio": 0.5, "base": 0.1, "novato": 0.1, "espia": 0.1, "bandido": 0.1, "estadistico": 0.1}}


# --- §2.5 y §2.6 ------------------------------------------------------------------------------

def test_beta_ejemplo_2_5():
    # k=7, n=10, m=0,3, s=20 -> p̂ = 13/30 = 43,3 %, σ = 8,9 %
    b = Beta(0.3, 20)
    for i in range(10):
        b.observar(i < 7, 1.0)                                       # λ=1: Bayes puro
    assert b.p == pytest.approx(13 / 30)
    assert b.sigma == pytest.approx(0.089, abs=0.001)
    assert (b.k, b.n) == (7, 10)


def test_olvido_hace_que_manden_las_observaciones_recientes():
    b = Beta(0.3, 20)
    for _ in range(300):
        b.observar(False, 0.98)
    bajo = b.p
    for _ in range(100):
        b.observar(True, 0.98)
    assert b.p > 0.5 > bajo                                           # con memoria ~50 manos, cambia de opinión
    sin_olvido = Beta(0.3, 20)
    for _ in range(300):
        sin_olvido.observar(False, 1.0)
    for _ in range(100):
        sin_olvido.observar(True, 1.0)
    assert sin_olvido.p < 0.3                                         # sin olvido pesa todo el pasado


def test_con_olvido_la_muestra_efectiva_queda_acotada_y_sigma_no_se_anula():
    b = Beta(0.3, 20)
    for i in range(5000):
        b.observar(i % 2 == 0, 0.98)                    # un rival que alterna: p ≈ 0,5
    assert b.alfa + b.beta <= 1 / (1 - 0.98) + 1e-6     # memoria efectiva ≈ 50 observaciones
    assert b.sigma > 0.05                               # nunca se vuelve "seguro": frena la explotación (§3.2)


# --- §2.7 huella --------------------------------------------------------------------------------

def test_cajas_de_z():
    cajas = HUELLA_TEX
    assert [caja_de_z(z, cajas) for z in (0.75, 0.40, 0.52, 0.8, 1.0, 0.0, 0.3, 0.45)] == [5, 1, 2, 8, 7, 8, 0, 8]


def test_huella_ejemplo_del_tex_0_75_0_4_0_75_es_base_con_93_por_ciento():
    post = posterior_huella([5, 1, 5], HUELLA_TEX)
    assert post["base"] == pytest.approx(0.93, abs=0.01)
    assert abs(sum(post.values()) - 1) < 1e-9


def test_huella_un_bot_propio_no_se_confunde_con_un_bot_del_kit():
    # Montos repartidos por todas las cajas: el posterior se va a "propio"
    post = posterior_huella([0, 3, 6, 2, 7, 4, 1], HUELLA_TEX)
    assert post["propio"] > 0.9


# --- Observador: mensajes -> eventos y estadísticas ------------------------------------------------

def jug(id_, silla, saldo, ap=0, activo=True, en_mano=True):
    return {"id": id_, "nombre": id_, "saldo": saldo, "apuesta_ronda": ap, "activo": activo, "en_torneo": True,
            "allin": False, "en_mano": en_mano, "posicion_silla": silla}


def estado(id_mano, etapa, pozo, apuesta, jugadores, historial, comunitarias=()):
    return {"id_mano": id_mano, "etapa": etapa, "comunitarias": [{"rango": C.rango_de(c), "palo": C.palo_de(c)} for c in comunitarias],
            "pozo": pozo, "apuesta_actual": apuesta, "subida_minima": 100, "ciega_chica": 50, "ciega_grande": 100,
            "posicion_boton": 0, "jugadores": jugadores, "historial_acciones": historial}


def acc(i, etapa, tipo, monto=None):
    a = {"tipo": tipo}
    if monto is not None:
        a["monto"] = monto
    return {"id_jugador": i, "etapa": etapa, "accion": a}


def nuevo_observador(tmp_path):
    mem = Memoria(P, str(tmp_path), persistir=True)
    return Observador(P, mem, mi_id="yo"), mem


def mano_con_flop(obs, id_mano, bet_a, board="Kh 7c 2s", mostrar=None):
    """yo (BTN, silla 0), a (SB), b (BB). Preflop: yo se retira... no: yo paga, a completa, b pasa. Flop: a apuesta bet_a, b paga, yo se retira."""
    base = [jug("yo", 0, 9900, 100), jug("a", 1, 9900, 100), jug("b", 2, 9900, 100)]
    obs.al_mensaje({"tipo": "mano_inicio", "cartas": [], "estado": estado(id_mano, "preflop", 150, 100,
                    [jug("yo", 0, 10000), jug("a", 1, 9950, 50), jug("b", 2, 9900, 100)], [])})
    h = [acc("yo", "preflop", "call"), acc("a", "preflop", "call"), acc("b", "preflop", "check")]
    for k in range(1, 4):
        obs.al_mensaje({"tipo": "estado", "estado": estado(id_mano, "preflop", 300, 100, base, h[:k])})
    tab = C.cartas_de_texto(board)
    sin = [jug("yo", 0, 9900), jug("a", 1, 9900), jug("b", 2, 9900)]
    obs.al_mensaje({"tipo": "estado", "estado": estado(id_mano, "flop", 300, 0, sin, h, tab)})
    h2 = h + [acc("a", "flop", "bet", bet_a)]
    con_a = [jug("yo", 0, 9900), jug("a", 1, 9900 - bet_a, bet_a), jug("b", 2, 9900)]
    obs.al_mensaje({"tipo": "estado", "estado": estado(id_mano, "flop", 300 + bet_a, bet_a, con_a, h2, tab)})
    h3 = h2 + [acc("b", "flop", "call")]
    con_b = [jug("yo", 0, 9900), jug("a", 1, 9900 - bet_a, bet_a), jug("b", 2, 9900 - bet_a, bet_a)]
    obs.al_mensaje({"tipo": "estado", "estado": estado(id_mano, "flop", 300 + 2 * bet_a, bet_a, con_b, h3, tab)})
    h4 = h3 + [acc("yo", "flop", "fold")]
    obs.al_mensaje({"tipo": "estado", "estado": estado(id_mano, "flop", 300 + 2 * bet_a, bet_a, con_b, h4, tab)})
    res = {"id_mano": id_mano, "repartos": [], "comunitarias": []}
    if mostrar:
        res["mostradas"] = {i: [{"rango": C.rango_de(c), "palo": C.palo_de(c)} for c in C.cartas_de_texto(t)] for i, t in mostrar.items()}
    obs.al_mensaje({"tipo": "mano_fin", "resultado": res})


def test_observador_calcula_z_y_actualiza_huella_y_sigue_ante_apuesta(tmp_path):
    obs, mem = nuevo_observador(tmp_path)
    mano_con_flop(obs, "m1", 225)                      # bet 225 en un pozo de 300: z = 0,75
    a, b = mem.rival("a"), mem.rival("b")
    assert a.n_z == 1 and a.contadores["cajas_z"][5] == 1          # caja .75
    assert a.contadores["post"]["apuestas"] == 1
    assert b.stats["sigue_grande"].n == 1 and b.stats["sigue_grande"].k == 1     # pagó una apuesta grande (z=.75 > .6)
    assert b.stats["sigue_chica"].n == 0
    assert mem.rival("yo").contadores["manos"] == 0                # a sí mismo no se modela


def test_apuesta_chica_se_cuenta_aparte(tmp_path):
    obs, mem = nuevo_observador(tmp_path)
    mano_con_flop(obs, "m1", 120)                      # z = 120/300 = 0,40
    assert mem.rival("a").contadores["cajas_z"][1] == 1
    assert mem.rival("b").stats["sigue_chica"].n == 1 and mem.rival("b").stats["sigue_grande"].n == 0


def test_vpip_pfr_y_tipo_preflop(tmp_path):
    obs, mem = nuevo_observador(tmp_path)
    mano_con_flop(obs, "m1", 225)
    a, b = mem.rival("a"), mem.rival("b")
    # a completó la ciega (paga): VPIP sí, PFR no; b pasó (ciega grande): VPIP no
    assert (a.stats["vpip"].k, a.stats["vpip"].n) == (1, 1) and a.stats["pfr"].k == 0
    assert (b.stats["vpip"].k, b.stats["vpip"].n) == (0, 1)
    assert a.contadores["preflop_fcr"]["C"] == 1 and a.contadores["manos"] == 1


def test_vpip_cuenta_manos_que_bender_no_juega(tmp_path):
    """Bender se retira en preflop; igual aprende de la mano (recibe los `estado`)."""
    obs, mem = nuevo_observador(tmp_path)
    ini = estado("m9", "preflop", 150, 100, [jug("yo", 0, 10000), jug("a", 1, 9950, 50), jug("b", 2, 9900, 100)], [])
    obs.al_mensaje({"tipo": "mano_inicio", "cartas": [], "estado": ini})
    h = [acc("yo", "preflop", "fold"), acc("a", "preflop", "raise", 300), acc("b", "preflop", "fold")]
    for k in range(1, 4):
        obs.al_mensaje({"tipo": "estado", "estado": estado("m9", "preflop", 150 + 250 * (k >= 2), 300 if k >= 2 else 100,
                                                          [jug("yo", 0, 10000, 0, False), jug("a", 1, 9700, 300), jug("b", 2, 9900, 100, k < 3)], h[:k])})
    obs.al_mensaje({"tipo": "mano_fin", "resultado": {"id_mano": "m9", "repartos": []}})
    a = mem.rival("a")
    assert a.stats["pfr"].k == 1 and a.stats["vpip"].k == 1 and a.contadores["preflop_fcr"]["R"] == 1


def test_varias_acciones_nuevas_en_un_solo_estado_se_reconstruyen(tmp_path):
    """Si llegan 2 acciones juntas (p. ej. tras una reconexión), el z de la 2.ª sale del modelo."""
    obs, mem = nuevo_observador(tmp_path)
    obs.al_mensaje({"tipo": "mano_inicio", "cartas": [], "estado": estado("m2", "preflop", 150, 100,
                    [jug("yo", 0, 10000), jug("a", 1, 9950, 50), jug("b", 2, 9900, 100)], [])})
    h = [acc("yo", "preflop", "call"), acc("a", "preflop", "call"), acc("b", "preflop", "check")]
    h += [acc("a", "flop", "bet", 150), acc("b", "flop", "raise", 450)]       # a: z = 150/300 = .5; b sube a 450
    tab = C.cartas_de_texto("Kh 7c 2s")
    base = [jug("yo", 0, 9900), jug("a", 1, 9750, 150), jug("b", 2, 9450, 450)]
    obs.al_mensaje({"tipo": "estado", "estado": estado("m2", "flop", 1050, 450, base, h, tab)})
    a, b = mem.rival("a"), mem.rival("b")
    assert a.contadores["cajas_z"][2] == 1                                   # caja .5
    # b sube a 450 sobre 150, con pozo 450 + lo que le falta (150): z = (450-150)/(450+150) = 0,5
    assert b.contadores["cajas_z"][2] == 1 and b.contadores["post"]["subidas"] == 1


def test_cartas_mostradas_mueven_la_creencia_de_tipo(tmp_path):
    obs, mem = nuevo_observador(tmp_path)
    riv = mem.rival("a")
    prior = riv.pi()
    board = tuple(sorted(C.cartas_de_texto("Kh 7c 2s")))
    combo = tuple(sorted(C.cartas_de_texto("Ks Kd")))                     # un set: categoría "fuerte"
    for _ in range(6):                                                    # a apuesta con el set en 6 showdowns
        obs.eventos = [{"id": "a", "etapa": "flop", "tipo": "bet", "enfrentaba": False, "z": 0.75, "z_enfrentada": None,
                        "allin": False, "board": board}]
        obs._tipo_con_cartas(riv, "a", combo)
    despues = riv.pi()
    assert riv.contadores["showdowns"] == 6
    # P(apuesta|fuerte): maníaco .95 > tag .65 > aleatorio .5 > nit .455 > station .39
    assert despues["maniaco"] / despues["station"] > prior["maniaco"] / prior["station"]
    assert despues["maniaco"] > prior["maniaco"] and despues["nit"] < prior["nit"] * 1.5
    assert abs(sum(despues.values()) - 1) < 1e-9 and min(despues.values()) >= P["piso_pi"] / 1.5
    # Y por el camino completo (mensajes + showdown) se registra el showdown y no se rompe nada
    mano_con_flop(obs, "mz", 225, mostrar={"a": "Ks Kd"})
    assert riv.contadores["showdowns"] == 7


def test_prior_preflop_ejemplo_del_tex_station_20_a_50_6(tmp_path):
    """§2.3: prior + 'entra pagando' lleva a station de 20 % a 50,6 % (con los priors y la tabla del .tex)."""
    p = cargar_params()
    p["prior_tipos"] = {"nit": .25, "tag": .25, "station": .20, "maniaco": .15, "aleatorio": .15}
    p["olvido"]["lambda"] = 1.0
    r = Rival("x", p)
    tabla = {"nit": .04, "tag": .06, "station": .50, "maniaco": .15, "aleatorio": .33}    # fila "entra pagando" del .tex
    r.obs_tipo({t: math.log(tabla[t]) for t in r.log_pi})
    assert r.pi()["station"] == pytest.approx(0.506, abs=0.002)


def test_persistencia_en_disco_entre_sesiones(tmp_path):
    obs, mem = nuevo_observador(tmp_path)
    mano_con_flop(obs, "m1", 225)
    p_antes = mem.rival("a").stats["vpip"].p
    mem2 = Memoria(P, str(tmp_path), persistir=True)                 # "otro proceso": carga del disco
    a2 = mem2.rival("a")
    assert a2.stats["vpip"].p == pytest.approx(p_antes) and a2.n_z == 1
    assert (tmp_path / "a.json").exists()


def test_sin_persistir_no_escribe(tmp_path):
    mem = Memoria(P, str(tmp_path), persistir=False)
    obs = Observador(P, mem, mi_id="yo")
    mano_con_flop(obs, "m1", 225)
    assert list(tmp_path.iterdir()) == []


def test_el_parametro_persistir_manda_cuando_no_se_pasa_explicito(tmp_path):
    p = cargar_params()
    p["rivales"].update({"dir": str(tmp_path), "persistir": False})
    mem = Memoria(p)
    mano_con_flop(Observador(p, mem, mi_id="yo"), "m1", 225)
    assert list(tmp_path.iterdir()) == []                       # no escribió nada
    p["rivales"]["persistir"] = True
    mem2 = Memoria(p)
    mano_con_flop(Observador(p, mem2, mi_id="yo"), "m1", 225)
    assert (tmp_path / "a.json").exists()


def test_un_mensaje_raro_no_rompe_al_observador(tmp_path):
    obs, mem = nuevo_observador(tmp_path)
    for msg in ({"tipo": "estado"}, {"tipo": "mano_fin"}, {"tipo": "otro"}, {"tipo": "estado", "estado": {}}):
        obs.al_mensaje(msg)


def test_bot_reconocido_con_huella_calibrada(tmp_path):
    p = cargar_params()
    p["huella"] = HUELLA_TEX                                           # la tabla provisional del .tex
    r = Rival("a", p)
    assert r.bot_reconocido() is None
    for caja in (5, 5, 1, 5, 1, 5, 5, 5):                              # montos de "base" en esa tabla
        r.obs_huella(caja)
    assert r.bot_reconocido() is not None and r.bot_reconocido()[0] == "base"


def test_la_huella_calibrada_separa_a_los_bots_del_kit():
    """Con la tabla calibrada (params.py), unas pocas apuestas típicas de cada bot bastan para reconocerlo."""
    h = P["huella"]
    sesgos = {"base": [1] * 6 + [5], "espia": [3, 2, 3, 3, 2, 3], "bandido": [4, 2, 4, 4, 2, 4]}   # cajas típicas
    for bot, cajas in sesgos.items():
        post = posterior_huella(cajas, h)
        assert max(post, key=post.get) == bot and post[bot] > 0.9, (bot, post)
    # montos al azar -> "propio" o "aleatorio", nunca un bot determinista con alta confianza
    post = posterior_huella([8, 8, 8, 8, 8, 8], h)
    assert post["aleatorio"] > 0.9
