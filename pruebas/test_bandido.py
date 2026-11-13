"""Capa 3, paso 2: el bandido online (bandido.py): brazos en sitio, shrinkage jerárquico, UCB, Exp3, recompensa y registro."""

import copy
import math

from bandido import Bandido
from params import cargar_params


class J:
    def __init__(self, id_, en_mano=True):
        self.id, self.en_mano = id_, en_mano


class Est:
    def __init__(self, ids, id_mano="m1"):
        self.jugadores = [J(i) for i in ids]
        self.id_mano = id_mano


class Reg:
    def __init__(self):
        self.filas = []

    def escribir(self, tipo, **campos):
        self.filas.append({"tipo": tipo, **campos})

    def de(self, tipo):
        return [f for f in self.filas if f["tipo"] == tipo]


class RivalFalso:
    def __init__(self, bot=None, tipo="station"):
        self.bot, self.tipo = bot, tipo

    def bot_reconocido(self):
        return (self.bot, 0.99) if self.bot else None

    def pi(self):
        return {t: (0.6 if t == self.tipo else 0.1) for t in ("nit", "tag", "station", "maniaco", "aleatorio")}


class MemoriaFalsa:
    def __init__(self, **por_id):
        self.por_id = por_id

    def rival(self, id_):
        return self.por_id.get(id_) or RivalFalso()


def params(selector="ucb", **cambios):
    p = cargar_params()
    p["bandido"]["activo"] = True
    p["bandido"]["selector"] = selector
    p["bandido"]["persistir"] = False
    p["bandido"].update(cambios)
    return p


def sin_bandido(p):
    return {k: v for k, v in p.items() if k != "bandido"}


# --- Brazos aplicados en sitio ---------------------------------------------------------------------------------------

def test_aplicar_un_brazo_cambia_los_parametros_en_sitio_y_base_los_restaura():
    p = params()
    original = copy.deepcopy(sin_bandido(p))
    top_pos, riesgo, cfg = p["apertura"]["top_pos"], p["riesgo"], p["bandido"]
    b = Bandido(p)
    b.aplicar("c05")
    assert p["riesgo"]["K"] == 6251 and p["olvido"]["lambda"] == 0.99432 and p["apertura"]["top_pos"]["BTN"] == 40.79
    assert p["apertura"]["top_pos"] is top_pos and p["riesgo"] is riesgo and p["bandido"] is cfg      # misma identidad: todos ven el cambio
    assert p["apertura"]["tamano_bb"] == 2.278
    b.aplicar("c24")
    assert p["riesgo"]["K"] == 5204 and p["decision"]["solo_valor_sobre_apuesta"] is False and p["apertura"]["top_pos"]["BTN"] == 43.38
    b.aplicar("base")
    assert sin_bandido(p) == original


def test_un_brazo_con_clave_mal_escrita_falla_al_crear_el_bandido():
    p = params()
    p["bandido"]["brazos"]["c05"]["riesgo"]["Kk"] = 1
    try:
        Bandido(p)
    except KeyError:
        return
    raise AssertionError("debía fallar")


def test_el_estado_de_los_brazos_no_toca_la_fuerza_del_prior_beta():
    p = params()
    for a in p["bandido"]["brazos"].values():
        assert "beta" not in a                     # s_prior se fija al crear al rival: no es un brazo


# --- Shrinkage jerárquico ----------------------------------------------------------------------------------------------

def test_shrinkage_rival_tipo_global_con_los_numeros_de_la_formula():
    b = Bandido(params(s_shrink=10.0))
    b._sumar("global", "g", "c05", 100, 0.0)               # n_g = 100, Q_g = 0
    b._sumar("tipo", "tipo:station", "c05", 30, 15.0)      # n_t = 30,  Q_t = 0,5
    b._sumar("rival", "r1", "c05", 10, 10.0)               # n_r = 10,  Q_r = 1
    q, d = b.q_jerarquico("r1", "tipo:station", "c05")
    assert math.isclose(d["Q_tipo"], (30 * 0.5 + 10 * 0.0) / 40)               # 0,375
    assert math.isclose(q, (10 * 1.0 + 10 * 0.375) / 20) and math.isclose(d["Q_rival"], 0.6875, abs_tol=1e-4)


def test_sin_datos_del_rival_manda_el_tipo_y_sin_datos_del_tipo_manda_el_global():
    b = Bandido(params(s_shrink=10.0))
    b._sumar("global", "g", "c05", 50, 25.0)               # Q_g = 0,5
    q, _ = b.q_jerarquico("nuevo", "tipo:tag", "c05")
    assert math.isclose(q, 0.5)                            # ni rival ni tipo: el global
    b._sumar("tipo", "tipo:tag", "c05", 40, 40.0)          # Q_t = 1
    q, _ = b.q_jerarquico("nuevo", "tipo:tag", "c05")
    assert math.isclose(q, (40 * 1.0 + 10 * 0.5) / 50)     # el tipo, encogido hacia el global
    assert b.q_jerarquico("nuevo", "tipo:tag", "c24")[0] == 0.0       # un brazo sin datos vale q0


def test_el_descuento_reduce_conteos_y_sumas_con_las_manos():
    b = Bandido(params(descuento=0.9))
    b._sumar("global", "g", "base", 1.0, 2.0)
    b.t = 2
    n, s = b._leer("global", "g", "base")
    assert math.isclose(n, 0.81) and math.isclose(s, 1.62)


# --- Selectores ----------------------------------------------------------------------------------------------------------

def test_ucb_prueba_primero_el_brazo_inicial_y_luego_los_demas_en_orden():
    p = params()
    reg = Reg()
    b = Bandido(p, reg, MemoriaFalsa())
    vistos = []
    for i in range(3):
        b.nueva_mano(Est(["yo", "r1"], f"m{i}"), "yo", {"yo": 10_000, "r1": 10_000})
        vistos.append(b.pendiente["brazo"])
    assert vistos == ["base", "c05", "c24"]


def test_ucb_con_datos_fuertes_elige_el_brazo_de_mayor_valor():
    b = Bandido(params())
    b._sumar("global", "g", "base", 200, 0.0)
    b._sumar("global", "g", "c05", 200, 60.0)
    b._sumar("global", "g", "c24", 200, -60.0)
    brazo, prob, info = b.elegir([], {}, {})
    assert brazo == "c05" and prob is None and info["explorar"] is True


def test_sin_explorar_contra_bots_del_kit_reconocidos():
    p = params()
    mem = MemoriaFalsa(r1=RivalFalso("base"), r2=RivalFalso("estadistico"))
    b = Bandido(p, Reg(), mem)
    b.nueva_mano(Est(["yo", "r1", "r2"]), "yo", {"yo": 10_000, "r1": 10_000, "r2": 10_000})
    assert b.pendiente["brazo"] == "base" and b.pendiente["explorar"] is False      # sin datos: el brazo inicial
    b.nueva_mano(Est(["yo", "r1", "r2"], "m2"), "yo", {"yo": 10_000, "r1": 10_000, "r2": 10_000})
    assert b.pendiente["brazo"] == "base" and b.pendiente["explorar"] is False      # y sigue sin probar otros
    b._sumar("global", "g", "c05", 50, 25.0)
    assert b.elegir(["r1", "r2"], {"r1": "bot:base", "r2": "bot:estadistico"}, {"r1": True, "r2": True})[0] == "c05"
    # con un solo rival NO reconocido en la mano sí se explora
    mem2 = MemoriaFalsa(r1=RivalFalso("base"), r2=RivalFalso(None))
    b2 = Bandido(params(), Reg(), mem2)
    b2.nueva_mano(Est(["yo", "r1", "r2"]), "yo", {"yo": 10_000, "r1": 10_000, "r2": 10_000})
    assert b2.pendiente["explorar"] is True
    # con explorar_vs_kit se explora siempre
    b3 = Bandido(params(explorar_vs_kit=True), Reg(), mem)
    b3.nueva_mano(Est(["yo", "r1", "r2"]), "yo", {"yo": 10_000, "r1": 10_000, "r2": 10_000})
    assert b3.pendiente["explorar"] is True


def test_exp3_respeta_el_piso_del_2_por_ciento_y_las_probabilidades_suman_uno():
    b = Bandido(params("exp3"))
    _, _, info = b.elegir([], {}, {})
    assert all(math.isclose(v, 1 / 3, abs_tol=1e-3) for v in info["indice"].values())            # sin datos: uniforme
    for a, g in (("base", 0.95), ("c05", 0.05), ("c24", 0.05)):
        b._sumar("global", "g", a, 200, 200 * g)                                  # un brazo domina por mucho
    _, _, info = b.elegir([], {}, {})
    p = info["indice"]
    assert math.isclose(sum(p.values()), 1.0, abs_tol=1e-3) and min(p.values()) >= 0.02 - 1e-3 and max(p, key=p.get) == "base"


def test_exp3_actualiza_todos_los_brazos_con_el_estimador_ponderado_por_1_sobre_p():
    reg = Reg()
    b = Bandido(params("exp3", descuento=1.0), reg, MemoriaFalsa())
    b.nueva_mano(Est(["yo", "r1"]), "yo", {"yo": 10_000, "r1": 10_000})
    a, prob = b.pendiente["brazo"], b.pendiente["prob"]
    assert prob is not None and prob >= 0.02
    b.nueva_mano(Est(["yo", "r1"], "m2"), "yo", {"yo": 10_500, "r1": 9_500})
    for a2 in b.orden:
        n, s = b._leer("global", "g", a2)
        assert math.isclose(n, 1.0)                                              # todos suman un paso
        assert (s > 0) if a2 == a else (s == 0.0)                                # solo el elegido trae ganancia estimada
    r = reg.de("bandido_recompensa")[0]
    gan = (max(-3.0, min(3.0, r["z"])) + 3.0) / 6.0
    assert math.isclose(b._leer("global", "g", a)[1], gan / prob, rel_tol=1e-3)


# --- Recompensa y registro -------------------------------------------------------------------------------------------

def test_la_recompensa_es_delta_ln_s_mas_k_con_las_fichas_de_la_mano_siguiente_y_se_registra():
    reg = Reg()
    p = params(K_recompensa=10_000, descuento=1.0)
    mem = MemoriaFalsa(r1=RivalFalso(None, "station"), r2=RivalFalso(None, "tag"))
    b = Bandido(p, reg, mem)
    b.nueva_mano(Est(["yo", "r1", "r2"]), "yo", {"yo": 10_000, "r1": 10_000, "r2": 10_000})
    ev = reg.de("bandido")[0]
    assert ev["brazo"] == "base" and ev["s"] == 10.0 and ev["selector"] == "ucb"
    assert {r["id"] for r in ev["rivales"]} == {"r1", "r2"} and all("Q_rival" in r["por_brazo"]["base"] for r in ev["rivales"])
    assert all(k in ev["rivales"][0]["por_brazo"]["base"] for k in ("Q_r", "Q_tipo", "Q_g", "n_r", "n_t", "n_g"))
    b.nueva_mano(Est(["yo", "r1", "r2"], "m2"), "yo", {"yo": 11_000, "r1": 9_000, "r2": 10_000})
    rec = reg.de("bandido_recompensa")[0]
    assert math.isclose(rec["r"], math.log(21_000) - math.log(20_000), abs_tol=1e-5) and rec["brazo"] == "base" and rec["z"] > 0
    n, s = b._leer("global", "g", "base")
    assert math.isclose(n, 1.0) and s > 0
    assert math.isclose(b._leer("rival", "r1", "base")[0], 1.0) and math.isclose(b._leer("tipo", "tipo:station", "base")[0], 1.0)
    assert b._leer("rival", "r1", "c05")[0] == 0.0                              # solo se acredita al brazo jugado


def test_el_tipo_se_acredita_una_vez_aunque_dos_rivales_lo_compartan():
    b = Bandido(params(descuento=1.0), Reg(), MemoriaFalsa())
    b.nueva_mano(Est(["yo", "r1", "r2"]), "yo", {"yo": 10_000, "r1": 10_000, "r2": 10_000})
    b.nueva_mano(Est(["yo", "r1", "r2"], "m2"), "yo", {"yo": 10_500, "r1": 10_000, "r2": 9_500})
    assert math.isclose(b._leer("tipo", "tipo:station", "base")[0], 1.0)           # ambos son station: una sola actualización
    assert math.isclose(b._leer("rival", "r1", "base")[0], 1.0) and math.isclose(b._leer("rival", "r2", "base")[0], 1.0)


def test_si_bender_no_juega_la_mano_no_se_elige_ni_se_liquida():
    b = Bandido(params(), Reg(), MemoriaFalsa())
    b.nueva_mano(Est(["r1", "r2"]), "yo", {"r1": 10_000, "r2": 10_000})
    assert b.pendiente is None and b.actual is None


# --- Persistencia y activación -----------------------------------------------------------------------------------------

def test_el_estado_se_guarda_y_se_recarga(tmp_path):
    p = params(persistir=True)
    p["rivales"]["dir"] = str(tmp_path)
    b = Bandido(p, Reg(), MemoriaFalsa())
    b._sumar("global", "g", "c05", 5, 2.0)
    b.t = 7
    b.guardar()
    p2 = params(persistir=True)
    p2["rivales"]["dir"] = str(tmp_path)
    b2 = Bandido(p2, Reg(), MemoriaFalsa())
    assert b2.t == 7 and b2._leer("global", "g", "c05")[0] > 4
    p3 = params("exp3", persistir=True)                      # otro selector: no se mezcla el estado
    p3["rivales"]["dir"] = str(tmp_path)
    assert Bandido(p3, Reg(), MemoriaFalsa()).t == 0


def test_por_defecto_el_bandido_esta_apagado_y_con_selector_fijo_el_bot_decide_con_los_parametros_base(tmp_path):
    from bot import Bender
    p = cargar_params()
    p["rivales"]["dir"] = str(tmp_path)
    assert p["bandido"]["activo"] is False and Bender(p, Reg()).bandido is None
    q = params("fijo")
    q["rivales"]["dir"] = str(tmp_path / "b")
    original = copy.deepcopy(sin_bandido(q))
    bot = Bender(q, Reg())
    assert bot.bandido is not None
    bot.bandido.nueva_mano(Est(["yo", "r1"]), "yo", {"yo": 10_000, "r1": 10_000})
    assert bot.bandido.pendiente["brazo"] == "base" and sin_bandido(q) == original
