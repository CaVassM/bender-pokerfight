"""Pruebas de estado.py: posiciones, aritmética de apuestas (port del SDK) y validación."""

from estado import (EstadoPublico, Jugador, Turno, accion_es_valida, accion_segura, posiciones,
                    texto_cartas)


def estado_con(sillas, boton, **extra):
    jugadores = [Jugador(id=f"j{s}", silla=s, saldo=10000, activo=True, en_torneo=True, en_mano=True) for s in sillas]
    return EstadoPublico(jugadores=jugadores, boton=boton, **extra)


def test_posiciones_seis_jugadores():
    pos = posiciones(estado_con(range(6), boton=2))
    # Horario desde el botón (silla 2): SB=3, BB=4, UTG=5, HJ=0, CO=1, BTN=2
    assert pos == {"j3": "SB", "j4": "BB", "j5": "UTG", "j0": "HJ", "j1": "CO", "j2": "BTN"}


def test_posiciones_cinco_sin_utg_y_con_hueco():
    pos = posiciones(estado_con([0, 1, 3, 4, 5], boton=5))    # la silla 2 está vacía
    assert pos == {"j0": "SB", "j1": "BB", "j3": "HJ", "j4": "CO", "j5": "BTN"}
    assert "UTG" not in pos.values()


def test_posiciones_heads_up_el_boton_es_ciega_chica():
    pos = posiciones(estado_con([1, 4], boton=4))
    assert pos == {"j1": "BB", "j4": "BTN/SB"}


def test_posiciones_ignora_a_quien_no_esta_en_mano():
    estado = estado_con(range(4), boton=0)
    estado.jugadores[2].en_mano = False
    assert posiciones(estado) == {"j1": "SB", "j3": "BB", "j0": "BTN"}


def turno(validas, saldo=1000, apuesta_ronda=0, apuesta_actual=0, subida_minima=100, pozo=150, rivales_saldo=1000):
    estado = EstadoPublico(
        pozo=pozo, apuesta_actual=apuesta_actual, subida_minima=subida_minima,
        jugadores=[Jugador(id="yo", saldo=saldo, apuesta_ronda=apuesta_ronda, activo=True, en_mano=True),
                   Jugador(id="r", saldo=rivales_saldo, activo=True, en_mano=True)])
    return Turno(estado, "yo", [(14, 3), (13, 3)], validas)


def test_apostar_pozo_respeta_la_subida_minima():
    t = turno(["fold", "check", "bet", "allin"])
    # medio pozo = 75 < subida mínima 100 -> se sube a 100
    assert t.apostar_pozo(0.5) == {"tipo": "bet", "monto": 100}
    assert t.apostar_pozo(1.0) == {"tipo": "bet", "monto": 150}


def test_apostar_el_techo_es_allin():
    t = turno(["fold", "check", "bet", "allin"])
    assert t.apostar(5000) == {"tipo": "allin"}
    assert t.apostar(1000) == {"tipo": "allin"}


def test_raise_es_total_no_incremento():
    # Ya puse 50, la apuesta actual es 300, subida mínima 200 -> mínimo total 500
    t = turno(["fold", "call", "raise", "allin"], saldo=950, apuesta_ronda=50, apuesta_actual=300, subida_minima=200, pozo=700)
    assert t.C == 250
    assert t.techo == 1000
    assert t.apostar(310) == {"tipo": "raise", "monto": 500}
    assert t.apostar(800) == {"tipo": "raise", "monto": 800}


def test_sin_poder_subir_cae_a_la_accion_pasiva():
    t = turno(["fold", "call"], apuesta_actual=300, pozo=700)
    assert t.apostar(900) == {"tipo": "call"}
    t = turno(["fold", "check"])
    assert t.apostar(900) == {"tipo": "check"}


def test_subida_minima_que_no_entra_en_el_stack_es_allin():
    t = turno(["fold", "call", "raise", "allin"], saldo=120, apuesta_actual=300, subida_minima=200, pozo=700)
    assert t.apostar(400) == {"tipo": "allin"}


def test_x_de_la_formula_1_8():
    t = turno(["fold", "call", "raise", "allin"], saldo=950, apuesta_ronda=50, apuesta_actual=300, subida_minima=200, pozo=700)
    # pozo si pagas = 700 + 250 = 950; monto 775 -> x = (775-300)/950 = 0,5
    assert t.pozo_si_pagas == 950
    assert abs(t.fraccion_de_monto(775) - 0.5) < 1e-9
    assert t.apostar_pozo(0.5) == {"tipo": "raise", "monto": 775}


def test_stack_efectivo_en_bb():
    t = turno(["fold", "check"], saldo=3000, rivales_saldo=5000)
    assert t.stack_efectivo_bb() == 3000 / 100
    t = turno(["fold", "check"], saldo=9000, rivales_saldo=2500)
    assert t.stack_efectivo_bb() == 25


def test_accion_segura_y_validacion():
    assert accion_segura(["fold", "check", "bet"]) == {"tipo": "check"}
    assert accion_segura(["fold", "call", "raise"]) == {"tipo": "fold"}
    assert accion_es_valida({"tipo": "check"}, ["fold", "check"])
    assert not accion_es_valida({"tipo": "call"}, ["fold", "check"])
    assert not accion_es_valida({"tipo": "raise"}, ["raise"])                    # falta el monto
    assert not accion_es_valida({"tipo": "raise", "monto": 100.5}, ["raise"])    # monto no entero
    assert accion_es_valida({"tipo": "raise", "monto": 100}, ["raise"])
    assert not accion_es_valida(None, ["fold"])


def test_texto_cartas():
    assert texto_cartas([(14, 3), (11, 2)]) == "As Jh"
