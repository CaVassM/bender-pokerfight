"""§1.4: S_ef con las fichas AL EMPEZAR LA MANO (S0), no con las que quedan detrás."""

from estado import EstadoPublico, Jugador, SeguimientoMesa, Turno


def test_stack_efectivo_no_se_hunde_porque_un_rival_vaya_all_in():
    """Un rival all-in tiene saldo 0 pero empezó la mano con 100 bb: S_ef sigue siendo 100 bb (antes salía 0 -> push/fold)."""
    estado = EstadoPublico(pozo=10_050, apuesta_actual=10_000, ciega_grande=100,
                           jugadores=[Jugador(id="yo", saldo=9_950, apuesta_ronda=50, activo=True, en_mano=True),
                                      Jugador(id="r", saldo=0, apuesta_ronda=10_000, activo=True, en_mano=True, allin=True)])
    sin_s0 = Turno(estado, "yo", [(14, 3), (14, 2)], ["fold", "call"])                       # estimado: saldo + apuesta_ronda
    con_s0 = Turno(estado, "yo", [(14, 3), (14, 2)], ["fold", "call"], stacks0={"yo": 10_000, "r": 10_000})
    assert sin_s0.stack_efectivo_bb() == 100 and con_s0.stack_efectivo_bb() == 100


def test_stack_efectivo_con_stack_corto_real_sigue_siendo_corto():
    estado = EstadoPublico(pozo=1_050, apuesta_actual=1_000, ciega_grande=100,
                           jugadores=[Jugador(id="yo", saldo=950, apuesta_ronda=50, activo=True, en_mano=True),
                                      Jugador(id="r", saldo=0, apuesta_ronda=1_000, activo=True, en_mano=True, allin=True)])
    assert Turno(estado, "yo", [], []).stack_efectivo_bb() == 10


def test_stack_efectivo_usa_a_todos_los_repartidos_aunque_se_hayan_retirado():
    """S0 y el modo quedan fijos durante la mano: el grande que se retiró sigue contando en max_i S0_i."""
    estado = EstadoPublico(ciega_grande=100,
                           jugadores=[Jugador(id="yo", saldo=3_000, activo=True, en_mano=True),
                                      Jugador(id="corto", saldo=500, activo=True, en_mano=True),
                                      Jugador(id="grande", saldo=0, activo=False, en_mano=True)])
    t = Turno(estado, "yo", [], [], stacks0={"yo": 3_000, "corto": 500, "grande": 9_000})
    assert t.stack_efectivo_bb() == 30                  # min(3 000, max(500, 9 000)) / 100


def test_seguimiento_guarda_las_fichas_del_inicio_de_la_mano():
    seg = SeguimientoMesa()
    estado = EstadoPublico(id_mano="m1", jugadores=[Jugador(id="yo", saldo=9_950, apuesta_ronda=50, en_mano=True),
                                                    Jugador(id="r", saldo=9_900, apuesta_ronda=100, en_mano=True),
                                                    Jugador(id="fuera", saldo=0, en_mano=False)])
    seg.nueva_mano(estado, [(14, 3), (14, 2)])
    assert seg.stacks0 == {"yo": 10_000, "r": 10_000}
    assert seg.stacks0_de(EstadoPublico(id_mano="m1")) == {"yo": 10_000, "r": 10_000}
    assert seg.stacks0_de(EstadoPublico(id_mano="otra")) is None                     # reconexión a mitad de otra mano
