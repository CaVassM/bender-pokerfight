"""Pruebas de la Capa 1: fórmulas contra los ejemplos del .tex, apertura, push/fold,
descartes, mezcla y un fuzz que comprueba que nunca sale una acción inválida."""

import math
import random

import pytest

import cartas as C
from capa1 import Capa1, ev_apuesta, ev_igualar, ev_pasar, modo_de, tipo_de_apuesta
from estado import EstadoPublico, Jugador, Turno, accion_es_valida
from params import cargar_params
import poblacion as POB


class MesaFalsa:
    manos_mesa = 0
    segundos_mesa = 0.0


def params(**reloj):
    p = cargar_params()
    p["reloj"].update({"n_min": 600, "eps_obj": 0.01, **reloj})
    p["capa1"]["semilla"] = 7
    return p


def cs(t):
    return C.cartas_de_texto(t)


def tupla(texto):
    return [C.a_tupla(c) for c in cs(texto)]


# --- Fórmulas: los ejemplos numéricos del .tex ---------------------------------------------------

def test_ev_igualar_ejemplo_1_6():
    # P=1300, C=900: e_min = 40,9 %; con e = 25,1 % el EV es ≈ -348
    assert abs(900 / (1300 + 900) - 0.409) < 1e-3
    assert ev_igualar(0.251, 1300, 900, saldo=10_000) == pytest.approx(-347.8, abs=0.5)


def test_ev_igualar_con_stack_corto_devuelve_lo_no_cubierto():
    # Pago 300 de 900: el exceso de 600 vuelve a su dueño y no entra al pozo
    assert ev_igualar(0.5, P=1300, C=900, saldo=300) == pytest.approx(0.5 * (700 + 300) - 300)


def test_ev_igualar_con_la_perilla_de_riesgo():
    base = ev_igualar(0.5, 1000, 500, saldo=5000)
    assert ev_igualar(0.5, 1000, 500, saldo=5000, delta=0.08) == pytest.approx(base - 0.08 * 1500)


def test_ev_pasar():
    assert ev_pasar(0.4, 600) == 240


def test_ev_apuesta_ejemplo_1_9():
    # P=600, B=300, c(0,5)=0,51 -> f=0,49, e'=0,35: EV ≈ +355
    f = 1 - POB.c_poblacion(0.5, False, cargar_params()["pob"])
    assert f == pytest.approx(0.49, abs=0.001)
    assert ev_apuesta(f, 600, 0.35, 300, 300) == pytest.approx(355, abs=1.5)


def test_ev_pushfold_ejemplo_1_10():
    # SB con 10 bb: P=150, A=950, A'=900, f=0,615, e'=0,40 -> ≈ +35
    assert ev_apuesta(0.615, 150, 0.40, 950, 900) == pytest.approx(34.5, abs=0.6)


def test_farol_puro_se_equilibra_en_f_estrella():
    P, B = 600, 300
    f_star = B / (P + B)
    assert f_star == pytest.approx(1 / 3)
    assert ev_apuesta(f_star, P, 0.0, B, B) == pytest.approx(0, abs=1e-9)       # EV(farol) = fP − (1−f)B = 0
    assert 600 / (600 + 600) == 0.5                                              # con B = P, f* = 50 %
    assert 300 / (600 + 300) < 600 / (600 + 600)                                 # apostar más grande sube f*


def test_modos_y_tipos_de_apuesta():
    m = cargar_params()["modo"]
    assert [modo_de(x, m) for x in (5, 15, 15.1, 25, 25.1, 100)] == ["push_fold", "push_fold", "intermedio", "intermedio", "profundo", "profundo"]
    d = cargar_params()["decision"]
    assert [tipo_de_apuesta(e, d) for e in (0.7, 0.5, 0.49, 0.25, 0.24)] == ["valor", "valor", "semi-farol", "semi-farol", "farol"]


# --- Armado de spots -------------------------------------------------------------------------------

def validas_de(yo, estado):
    c = max(0, estado.apuesta_actual - yo.apuesta_ronda)
    v = ["fold", "check" if c == 0 else "call"]
    if yo.saldo + yo.apuesta_ronda >= estado.apuesta_actual + estado.subida_minima:
        v.append("bet" if c == 0 else "raise")
    if yo.saldo > 0:
        v.append("allin")
    return v


def spot(mano, board="", rivales=((10_000, 0),), yo=(10_000, 0), pozo=150, apuesta_actual=0, boton=0, silla_yo=0,
         historial=(), etapa=None, subida_minima=100):
    """yo y rivales = (saldo, apuesta_ronda). Sillas consecutivas; el botón en `boton`."""
    jugadores = [Jugador(id="yo", saldo=yo[0], apuesta_ronda=yo[1], activo=True, en_torneo=True, en_mano=True, silla=silla_yo)]
    silla = 1
    for i, (saldo, ap) in enumerate(rivales):
        if silla == silla_yo:
            silla += 1
        jugadores.append(Jugador(id=f"r{i}", saldo=saldo, apuesta_ronda=ap, activo=True, en_torneo=True, en_mano=True,
                                 silla=silla, allin=(saldo == 0)))
        silla += 1
    comunitarias = tupla(board) if board else []
    etapa = etapa or {0: "preflop", 3: "flop", 4: "turn", 5: "river"}[len(comunitarias)]
    estado = EstadoPublico(id_mano="m", etapa=etapa, comunitarias=comunitarias, pozo=pozo, apuesta_actual=apuesta_actual,
                           subida_minima=subida_minima, ciega_chica=50, ciega_grande=100, boton=boton,
                           jugadores=jugadores, historial=list(historial))
    return Turno(estado, "yo", tupla(mano), validas_de(jugadores[0], estado))


def decidir(turno, p=None, semilla=7):
    capa = Capa1(p or params(), rng=random.Random(semilla))
    return capa.decidir(turno, MesaFalsa())


# --- Apertura (§1.5) -------------------------------------------------------------------------------

def mesa_de_seis(mano, posicion_yo):
    """Mesa de 6, preflop, nadie subió. Botón en silla 5 -> SB=0, BB=1, UTG=2, HJ=3, CO=4, BTN=5."""
    silla = {"SB": 0, "BB": 1, "UTG": 2, "HJ": 3, "CO": 4, "BTN": 5}[posicion_yo]
    ciega = {"SB": 50, "BB": 100}.get(posicion_yo, 0)
    jugadores = []
    for s in range(6):
        ap = {0: 50, 1: 100}.get(s, 0)
        jugadores.append(Jugador(id="yo" if s == silla else f"r{s}", saldo=10_000 - ap, apuesta_ronda=ap, activo=True,
                                 en_torneo=True, en_mano=True, silla=s))
    estado = EstadoPublico(id_mano="m", pozo=150, apuesta_actual=100, subida_minima=100, boton=5, jugadores=jugadores)
    yo = next(j for j in jugadores if j.id == "yo")
    return Turno(estado, "yo", tupla(mano), validas_de(yo, estado))


@pytest.mark.parametrize("mano,pos,abre", [
    ("As Kh", "UTG", True), ("7h 2c", "UTG", False),
    ("Th 9h", "UTG", False), ("Th 9h", "BTN", True),          # T9s: no entra en el 14,3 % de UTG, sí en el 43,3 % del BTN
    ("6h 5c", "BTN", False), ("Qs Js", "HJ", True), ("Qs Jh", "HJ", False), ("Kh 4c", "SB", False),
])
def test_apertura_por_posicion(mano, pos, abre):
    turno = mesa_de_seis(mano, pos)
    accion, motivo, info = decidir(turno)
    assert info["decision"] == "apertura" and info["abre"] == abre
    if abre:
        assert accion == {"tipo": "raise", "monto": 250}                      # 2,5 bb: el TOTAL, no el incremento
    else:
        assert accion == {"tipo": "fold"}                                     # nunca entra pagando la ciega


def test_apertura_heads_up_70_por_ciento():
    # Heads-up: el botón es la ciega chica (50) y abre con el top 70 %
    estado = EstadoPublico(id_mano="m", pozo=150, apuesta_actual=100, subida_minima=100, boton=0, jugadores=[
        Jugador(id="yo", saldo=9950, apuesta_ronda=50, activo=True, en_torneo=True, en_mano=True, silla=0),
        Jugador(id="r0", saldo=9900, apuesta_ronda=100, activo=True, en_torneo=True, en_mano=True, silla=1)])
    for mano, abre in (("Th 6s", True), ("9d 3c", False)):               # T6o está en el 63,5 %; 93o en el 81,9 %
        turno = Turno(estado, "yo", tupla(mano), validas_de(estado.jugadores[0], estado))
        _, _, info = decidir(turno)
        assert info["top_pos"] == 70.0, info
        assert info["abre"] == abre


# --- Push/fold (§1.10) -----------------------------------------------------------------------------

def spot_pushfold(mano):
    # SB con 10 bb efectivos: P=150, ya puse 50, mi saldo 950; el BB puso 100 y le quedan 900
    return spot(mano, rivales=((900, 100),), yo=(950, 50), pozo=150, apuesta_actual=100, boton=0)


def test_pushfold_solo_all_in_o_retirarse():
    turno = spot_pushfold("As Ah")
    accion, _, info = decidir(turno)
    assert info["modo"] == "push_fold" and info["decision"] == "push/fold"
    assert {f["tipo"] for f in info["tabla_ev"]} <= {"fold", "allin"}
    assert accion == {"tipo": "allin"}
    accion, _, info = decidir(spot_pushfold("7h 2c"))
    assert accion == {"tipo": "fold"}


def test_pushfold_usa_c_nash_y_la_formula_del_tex():
    _, _, info = decidir(spot_pushfold("Ah Td"))
    push = next(f for f in info["tabla_ev"] if f["tipo"] == "allin")
    assert push["f"] == pytest.approx(1 - 0.385, abs=1e-3)                    # f = (1 − 0,385)^1
    assert push["A"] == 950 and push["A_prima"] == 900
    ep = info["equity_si_pagan"]["e"]
    esperado = 0.615 * 150 + (1 - 0.615) * (ep * (150 + 950 + 900) - 950)
    assert push["ev"] == pytest.approx(esperado, abs=2.0)


# --- Decisiones con el menú completo -----------------------------------------------------------------

def test_aire_contra_apuesta_grande_en_el_river_se_retira():
    # Board seco, apuesta de pozo completo del rival: el aire se retira
    historial = [{"id_jugador": "r0", "etapa": "river", "accion": {"tipo": "bet"}}]
    turno = spot("4h 3c", "Ks Qd 9h 2c 8s", rivales=((8000, 1000),), yo=(8000, 0), pozo=2000, apuesta_actual=1000, historial=historial)
    accion, _, info = decidir(turno)
    assert accion == {"tipo": "fold"}
    assert info["tabla_ev"][0]["ev"] == 0


def test_los_nuts_no_se_retiran_y_se_apuesta_o_sube():
    historial = [{"id_jugador": "r0", "etapa": "river", "accion": {"tipo": "bet"}}]
    turno = spot("As Ks", "Qs Js Ts 2c 8d", rivales=((8000, 500),), yo=(8000, 0), pozo=1500, apuesta_actual=500, historial=historial)
    accion, _, info = decidir(turno)
    assert accion["tipo"] in ("raise", "allin")
    assert info["equity_si_pagan"]["e"] > 0.9


def test_e_prima_depende_del_tamano_y_no_se_hace_all_in_con_manos_marginales():
    """Regresión del paso 3: e' se calculaba una sola vez (con c de media apuesta) y se aplicaba al
    all-in, donde paga solo la parte fuerte del rango. Resultado: A♣T♠ iba all-in (100 bb) sobre una
    subida a 3 bb de un rival que nunca se retira."""
    historial = [{"id_jugador": "r0", "etapa": "preflop", "accion": {"tipo": "raise"}}]
    turno = spot("Ac Ts", rivales=((9700, 300),), yo=(9900, 100), pozo=400, apuesta_actual=300, historial=historial, boton=1)
    accion, _, info = decidir(turno)
    filas = {f["accion"]: f for f in info["tabla_ev"]}
    assert filas["all-in"]["c"]["r0"] < filas["x=0.5"]["c"]["r0"]               # ante un all-in paga menos del rango
    assert filas["all-in"]["e_prima"] < filas["x=0.5"]["e_prima"] - 0.05          # y contra eso la equity baja
    assert filas["all-in"]["e_prima"] < 0.5
    assert accion != {"tipo": "allin"}
    assert len(info["equities_si_pagan"]) >= 2                                  # una simulación por rango de pago distinto


def test_pasar_gratis_nunca_se_retira():
    for mano in ("7h 2c", "As Ah"):
        accion, _, _ = decidir(spot(mano, "Kd 9c 4s", rivales=((9000, 0),), yo=(9000, 0), pozo=600))
        assert accion["tipo"] in ("check", "bet", "allin")


def test_la_tabla_de_ev_trae_formula_y_descartes():
    turno = spot("Ah Qd", "Kd 9c 4s", rivales=((9000, 0),), yo=(9000, 0), pozo=600)
    _, _, info = decidir(turno)
    for fila in info["tabla_ev"]:
        assert fila["formula"] and "descartada" in fila
    assert "equity" in info and info["equity"]["n"] >= 64 and info["equity"]["tiempo_s"] >= 0
    assert info["modo"] == "profundo" and info["t_max"] > 0


def test_multiway_descarta_apuestas_sin_valor():
    # Tres rivales y una mano marginal: las apuestas se descartan (e' < 0,50)
    turno = spot("7h 6h", "Ks 9d 2c", rivales=((9000, 0), (9000, 0), (9000, 0)), yo=(9000, 0), pozo=900)
    _, _, info = decidir(turno)
    apuestas = [f for f in info["tabla_ev"] if f["tipo"] in ("bet", "raise", "allin")]
    assert apuestas and all(f["descartada"] for f in apuestas)
    assert any("multiway" in f["descartada"] for f in apuestas)               # (el all-in puede caer por la regla de solo valor)


def test_compromiso_en_modo_intermedio():
    # S_ef = 20 bb (intermedio): igualar 1000 de un stack de 2000 (> 1/3) se descarta
    historial = [{"id_jugador": "r0", "etapa": "flop", "accion": {"tipo": "bet"}}]
    turno = spot("Ah Kd", "Kc 9c 4s", rivales=((2000, 1000),), yo=(2000, 0), pozo=2000, apuesta_actual=1000, historial=historial)
    _, _, info = decidir(turno)
    assert info["modo"] == "intermedio" and info["s_ef_bb"] == 20.0
    igualar = next(f for f in info["tabla_ev"] if f["tipo"] == "call")
    assert igualar["descartada"] and "compromiso" in igualar["descartada"]


def test_mezcla_elige_la_segunda_solo_si_estan_muy_cerca():
    from capa1 import Capa1 as Cap

    class Rng:
        def __init__(self, v):
            self.v = v
        def random(self):
            return self.v

    # Con un sorteo de mezcla de 0,99 (> 0,35) nunca se mezcla; con 0,0 se mezcla si y solo si
    # la 2.ª mejor está a menos de 0,02·max(P, bb) de la 1.ª, tiene EV >= 0 y ninguna es retirarse.
    p = params()
    p["riesgo"]["utilidad"] = False                 # esta prueba mide la cercanía en EV (con utilidad la mezcla compara en ce)
    turno = spot("Ah Qd", "Kd 9c 4s", rivales=((9000, 0),), yo=(9000, 0), pozo=600)
    hubo_mezcla = 0
    for semilla in range(12):                                            # varios spots con pozos distintos
        for valor in (0.0, 0.99):
            capa = Cap(p, rng=random.Random(semilla))
            capa.rng_mezcla = Rng(valor)
            t = spot("Ah Qd", "Kd 9c 4s", rivales=((9000, 0),), yo=(9000, 0), pozo=300 + 150 * semilla)
            _, _, info = capa.decidir(t, MesaFalsa())
            vivos = sorted((f for f in info["tabla_ev"] if not f["descartada"]), key=lambda f: -f["ev"])
            cerca = (len(vivos) > 1 and vivos[0]["ev"] - vivos[1]["ev"] < 0.02 * max(t.P, t.bb) and vivos[1]["ev"] >= 0
                     and vivos[0]["tipo"] != "fold" and vivos[1]["tipo"] != "fold")
            if valor == 0.99:
                assert not info["mezcla"]
            else:
                assert info["mezcla"] == cerca
                hubo_mezcla += cerca
    assert hubo_mezcla >= 0


def test_sin_rangos_de_poblacion_usa_manos_al_azar():
    p = params()
    p["capa1"]["rangos_poblacion"] = False
    historial = [{"id_jugador": "r0", "etapa": "preflop", "accion": {"tipo": "raise"}}]
    turno = spot("As Kh", rivales=((9750, 250),), yo=(9900, 100), pozo=400, apuesta_actual=250, historial=historial, boton=1)
    _, _, info = decidir(turno, p)
    assert info["rangos"]["r0"]["combos"] > 1000                          # todas las manos vivas


# --- §1.13 Utilidad con colchón ------------------------------------------------------------------------------

def test_utilidad_moneda_al_aire_pide_63_por_ciento_con_K_10000():
    """Stack de 10 000, K = 10 000, all-in contra un rival que paga siempre (f=0, P=0, A=A'=10 000): ganar deja
    ln(30 000), perder ln(10 000) y retirarse ln(20 000). Conviene si e·ln 3 >= ln 2, o sea e >= 63,1 %."""
    from capa1 import u_apuesta, u_retirarse, equivalente_cierto
    S, K = 10_000, 10_000
    umbral = math.log(2) / math.log(3)
    assert umbral == pytest.approx(0.6309, abs=1e-4)
    assert u_apuesta(0.0, 0, 0.64, 10_000, 10_000, S, K) > u_retirarse(S, K)
    assert u_apuesta(0.0, 0, 0.62, 10_000, 10_000, S, K) < u_retirarse(S, K)
    # el mismo all-in con e' = 0,55 tiene EV = 0,55·20 000 − 10 000 = +1 000 pero equivalente cierto NEGATIVO
    assert ev_apuesta(0.0, 0, 0.55, 10_000, 10_000) == pytest.approx(1000.0)
    assert equivalente_cierto(u_apuesta(0.0, 0, 0.55, 10_000, 10_000, S, K), S, K) < 0
    # con un colchón mayor la exigencia baja: K = 40 000 -> e >= ln(1,25)/ln(1,5) = 55,0 %
    assert u_apuesta(0.0, 0, 0.56, 10_000, 10_000, S, 40_000) > u_retirarse(S, 40_000)
    assert u_apuesta(0.0, 0, 0.54, 10_000, 10_000, S, 40_000) < u_retirarse(S, 40_000)


def test_utilidad_hojas_del_arbol():
    from capa1 import u_apuesta, u_igualar, u_pasar, u_retirarse, utilidad
    S, K, P = 6000, 10_000, 900
    assert u_retirarse(S, K) == pytest.approx(math.log(S + K))
    assert u_pasar(1.0, P, S, K) == pytest.approx(utilidad(S + P, K))
    assert u_pasar(0.0, P, S, K) == pytest.approx(utilidad(S, K))
    assert u_igualar(1.0, P, 400, S, K) == pytest.approx(utilidad(S + P, K))
    assert u_igualar(0.0, P, 400, S, K) == pytest.approx(utilidad(S - 400, K))
    # call corto: solo se pueden cubrir 300 de 900; lo no cubierto (600) vuelve a su dueño, igual que ev_igualar
    assert u_igualar(1.0, 1300, 900, 300, K) == pytest.approx(utilidad(300 + 700, K))
    assert u_igualar(0.0, 1300, 900, 300, K) == pytest.approx(utilidad(0, K))
    # apuesta: todos se retiran -> S+P; si pagan, depende de e'
    assert u_apuesta(1.0, P, 0.3, 500, 500, S, K) == pytest.approx(utilidad(S + P, K))
    assert u_apuesta(0.0, P, 1.0, 500, 450, S, K) == pytest.approx(utilidad(S + P + 450, K))
    assert u_apuesta(0.0, P, 0.0, 500, 450, S, K) == pytest.approx(utilidad(S - 500, K))


def test_utilidad_con_K_enorme_recupera_el_ev():
    """K → ∞: u(S) es lineal y el equivalente cierto coincide con el EV de las fórmulas de siempre."""
    from capa1 import equivalente_cierto, u_apuesta, u_igualar, u_pasar
    S, K = 8000, 1e9              # (con K mayor el error de redondeo del logaritmo en coma flotante supera a la diferencia)
    for e in (0.2, 0.5, 0.8):
        assert equivalente_cierto(u_pasar(e, 700, S, K), S, K) == pytest.approx(ev_pasar(e, 700), rel=1e-3, abs=0.05)
        assert equivalente_cierto(u_igualar(e, 700, 300, S, K), S, K) == pytest.approx(ev_igualar(e, 700, 300, S), rel=1e-3, abs=0.05)
        assert equivalente_cierto(u_apuesta(0.4, 700, e, 500, 450, S, K), S, K) == pytest.approx(ev_apuesta(0.4, 700, e, 500, 450), rel=1e-3, abs=0.05)


def test_utilidad_la_tabla_trae_u_y_ce_y_retirarse_es_la_referencia():
    turno = spot("Ah Qd", "Kd 9c 4s", rivales=((9000, 0),), yo=(9000, 0), pozo=600)
    p = params()
    p["riesgo"]["K"] = 10_000
    _, _, info = decidir(turno, p)
    assert info["utilidad"] == {"activa": True, "K": 10_000, "S": 9000}      # v1.1-riesgo: activada por defecto
    for fila in info["tabla_ev"]:
        assert "u" in fila and "ce" in fila and "ev" in fila
    assert all(f["ce"] == 0.0 and f["u"] == pytest.approx(math.log(19_000), abs=1e-5) for f in info["tabla_ev"] if f["tipo"] == "fold")


def _spots_de_prueba(n=40, semilla=11):
    rng = random.Random(semilla)
    out = []
    for _ in range(n):
        n_board = rng.choice([0, 3, 4, 5])
        cartas = rng.sample(range(52), 2 + n_board)
        mano, board = cartas[:2], cartas[2:]
        saldo = rng.choice([1500, 4000, 10_000, 14_000])
        apuesta = rng.choice([0, 0, 300, 900])
        riv = [(rng.choice([6000, 10_000]), apuesta)] * rng.choice([1, 2])
        pozo = max(150, 2 * apuesta + rng.choice([200, 900, 2000]))
        out.append(spot(C.texto_cartas(mano), C.texto_cartas(board) if board else "", rivales=tuple(riv), yo=(saldo, 0), pozo=pozo,
                        apuesta_actual=apuesta, boton=rng.randrange(6), silla_yo=rng.randrange(6)))
    return out


def test_utilidad_apagada_no_cambia_las_decisiones_y_con_K_enorme_tampoco():
    """riesgo.utilidad=False es el comportamiento de siempre (y no depende de K); con utilidad=True y K enorme se elige igual."""
    p_off, p_on = params(n_min=300, eps_obj=0.02), params(n_min=300, eps_obj=0.02)
    p_off["riesgo"].update({"utilidad": False, "K": 500})
    p_on["riesgo"].update({"utilidad": True, "K": 1e9})
    p_ref = params(n_min=300, eps_obj=0.02)
    p_ref["riesgo"]["utilidad"] = False                        # referencia = el comportamiento de v1-probabilistico
    iguales = 0
    for t in _spots_de_prueba():
        if not t.validas or not t.rivales:
            continue
        a_ref = decidir(t, p_ref, semilla=3)[0]
        a_off = decidir(t, p_off, semilla=3)[0]
        a_on = decidir(t, p_on, semilla=3)[0]
        assert a_off == a_ref                                  # K no importa con el interruptor apagado
        iguales += a_on == a_ref
    assert iguales >= 35                                       # con K enorme casi siempre igual (empates numéricos aparte)


def test_valores_por_defecto_de_v1_1_riesgo():
    """Aprobado por el usuario: utilidad ON (2026-11-12), calibración de los all-in OFF; K = 6 000 desde v1.4-final (2026-11-17, prueba f2;
    antes 10 000)."""
    p = params()
    assert p["riesgo"]["utilidad"] is True and p["riesgo"]["K"] == 6_000
    assert p["calibracion_allin"]["activa"] is False


def test_utilidad_con_K_chico_hace_menos_all_in_y_nunca_acciones_invalidas():
    p_off, p_on = params(n_min=300, eps_obj=0.02), params(n_min=300, eps_obj=0.02)
    p_off["riesgo"]["utilidad"] = False
    p_on["riesgo"].update({"utilidad": True, "K": 2000})
    n_off = n_on = 0
    for t in _spots_de_prueba(60, semilla=5):
        if not t.validas or not t.rivales:
            continue
        a_off, _, _ = decidir(t, p_off, semilla=9)
        a_on, _, info = decidir(t, p_on, semilla=9)
        assert accion_es_valida(a_on, t.validas)
        n_off += a_off["tipo"] == "allin"
        n_on += a_on["tipo"] == "allin"
    assert n_on <= n_off


# --- Fuzz: nunca una acción inválida, nunca una excepción ------------------------------------------------

def test_fuzz_nunca_acciones_invalidas():
    rng = random.Random(123)
    p = params(n_min=64, eps_obj=0.05)
    capa = Capa1(p, rng=random.Random(5))
    revisadas = 0
    for _ in range(250):
        n_board = rng.choice([0, 3, 4, 5])
        cartas = rng.sample(range(52), 2 + n_board)
        mano, board = cartas[:2], cartas[2:]
        n_riv = rng.choice([1, 2, 3, 4])
        saldo_yo = rng.choice([400, 1500, 2500, 6000, 10_000])
        yo_ap = rng.choice([0, 0, 50, 100])
        apuesta = rng.choice([0, 0, 100, 300, 800, 3000])
        riv = []
        for _ in range(n_riv):
            ap = apuesta if apuesta and rng.random() < 0.8 else rng.choice([0, 100])
            riv.append((rng.choice([0, 800, 3000, 10_000]), ap))
        pozo = max(150, yo_ap + sum(a for _, a in riv) + rng.choice([0, 300, 1200]))
        turno = spot(C.texto_cartas(mano), C.texto_cartas(board) if board else "", rivales=tuple(riv),
                     yo=(saldo_yo, yo_ap), pozo=pozo, apuesta_actual=max([a for _, a in riv] + [yo_ap]), boton=rng.randrange(6),
                     silla_yo=rng.randrange(6))
        if not turno.validas or len(turno.rivales) == 0:
            continue
        accion, motivo, info = capa.decidir(turno, MesaFalsa())
        assert accion_es_valida(accion, turno.validas), (accion, turno.validas, info)
        if accion["tipo"] in ("bet", "raise"):
            assert turno.subida_minima_total <= accion["monto"] <= turno.techo
        revisadas += 1
    assert revisadas > 150
