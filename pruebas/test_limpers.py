"""§1.5 "Preflop con limpers": nadie subió pero alguien igualó la ciega. Iso-raise, over-limp, ciega grande y apertura vs station."""

import random

from test_capa1 import MesaFalsa, decidir, params, spot


def p_limp(**cambios):
    p = params(n_min=500, eps_obj=0.02)
    p["apertura"]["limpers_menu"] = True
    p["apertura"].update(cambios)
    return p


def llamadas(*ids):
    return [{"id_jugador": i, "etapa": "preflop", "accion": {"tipo": "call"}} for i in ids]


def spot_btn(mano, n_lim=2, saldo=10_000):
    """Bender en el botón (silla 0); r0 = SB (silla 1), r1 = BB (silla 2), r2 y r3 = HJ y CO (sillas 3 y 4); los últimos n_lim igualaron."""
    riv = [(9950, 50), (9900, 100)] + [(9900, 100)] * n_lim
    riv += [(10_000, 0)] * (4 - len(riv))
    return spot(mano, rivales=tuple(riv), yo=(saldo, 0), pozo=150 + 100 * n_lim, apuesta_actual=100, boton=0,
                historial=llamadas(*[f"r{i}" for i in range(2, 2 + n_lim)]))


def spot_bb(mano):
    """Bender en la ciega grande (silla 0, botón en la 3): r0, r1 y r2 igualaron, r3 es la SB. Pasar es gratis."""
    riv = [(9900, 100), (9900, 100), (9900, 100), (9950, 50)]
    return spot(mano, rivales=tuple(riv), yo=(9900, 100), pozo=450, apuesta_actual=100, boton=3,
                historial=llamadas("r0", "r1", "r2"))


def test_detecta_limpers_y_no_los_hay_si_hubo_subida():
    t = spot_btn("As Kd", 2)
    assert [r.id for r in t.limpers()] == ["r2", "r3"]
    assert spot_btn("As Kd", 0).limpers() == []
    subida = spot("As Kd", rivales=((9500, 500), (9900, 100)), yo=(10_000, 0), pozo=750, apuesta_actual=500, boton=0,
                  historial=llamadas("r1"))
    assert subida.limpers() == []                       # ya hubo subida: no es un pozo limpeado


def test_con_dos_limpers_iso_sube_con_AK_iguala_con_55_y_se_retira_con_72o():
    accion, _, info = decidir(spot_btn("As Kd"), p_limp())
    assert accion == {"tipo": "raise", "monto": 450}            # 2,5 bb de apertura + 1 bb por cada limper = 4,5 bb
    assert info["limpers"]["n"] == 2 and info["limpers"]["iso_bb"] == 4.5
    assert next(f for f in info["tabla_ev"] if f["accion"] == "iso-raise")["descartada"] is None
    accion, _, info = decidir(spot_btn("5s 5c"), p_limp())
    assert accion == {"tipo": "call"}                           # over-limp en posición
    accion, _, _ = decidir(spot_btn("7h 2c"), p_limp())
    assert accion == {"tipo": "fold"}


def test_tamano_del_iso_es_apertura_mas_iso_por_limper():
    assert decidir(spot_btn("Qs Qd", 1), p_limp())[0] == {"tipo": "raise", "monto": 350}            # 2,5 + 1·1
    assert decidir(spot_btn("Qs Qd", 2), p_limp(iso_por_limper=2.0))[0] == {"tipo": "raise", "monto": 650}   # 2,5 + 2·2
    assert decidir(spot_btn("Qs Qd", 2), p_limp(tamano_bb=3.0))[0] == {"tipo": "raise", "monto": 500}        # 3 + 1·2


def test_ciega_grande_sin_subida_nunca_se_retira():
    for mano in ("7h 2c", "9s 3d", "Jc 4h"):
        for limpers_menu in (True, False):
            accion, _, info = decidir(spot_bb(mano), p_limp(limpers_menu=limpers_menu))
            assert accion["tipo"] != "fold", (mano, limpers_menu)
            assert all(f["tipo"] != "fold" for f in info["tabla_ev"])
    assert decidir(spot_bb("7h 2c"), p_limp())[0] == {"tipo": "check"}


def test_en_profundo_no_se_ofrece_el_all_in_sobre_limpers_y_en_intermedio_si():
    _, _, info = decidir(spot_btn("As Kd"), p_limp())
    assert info["modo"] == "profundo" and all(f["tipo"] != "allin" for f in info["tabla_ev"])
    _, _, info = decidir(spot_btn("As Kd", saldo=2_000), p_limp())                 # 20 bb: intermedio
    assert info["modo"] == "intermedio" and any(f["tipo"] == "allin" for f in info["tabla_ev"])
    _, _, info = decidir(spot_btn("As Kd"), p_limp(limpers_allin_profundo=True))
    assert any(f["tipo"] == "allin" for f in info["tabla_ev"])


def test_por_defecto_la_regla_de_limpers_esta_encendida_y_apagada_es_la_tabla_de_siempre():
    assert params()["apertura"]["limpers_menu"] is True                        # v1.3-limpers
    p = params(n_min=500, eps_obj=0.02)
    p["apertura"]["limpers_menu"] = False
    accion, _, info = decidir(spot_btn("As Kd"), p)
    assert info["decision"] == "apertura" and accion == {"tipo": "raise", "monto": 250} and "limpers" not in info
    accion, _, info = decidir(spot_btn("7h 2c"), p)
    assert info["decision"] == "apertura" and accion == {"tipo": "fold"}


def test_sin_limpers_sigue_la_tabla_de_apertura_aunque_el_interruptor_este_encendido():
    accion, _, info = decidir(spot_btn("As Kd", 0), p_limp())
    assert info["decision"] == "apertura" and accion == {"tipo": "raise", "monto": 250}


# --- apertura_vs_station ---------------------------------------------------------------------------------------------

class MemoriaFalsa:
    def __init__(self, pi_station):
        self.pi_station = pi_station

    def pi(self, _id):
        return {"station": self.pi_station, "tag": 1 - self.pi_station}


def capa_con(pi_station, **cambios):
    from capa1 import Capa1
    p = params(n_min=500, eps_obj=0.02)
    p["apertura"].update(cambios)
    return Capa1(p, rng=random.Random(7), memoria=MemoriaFalsa(pi_station))


def test_apertura_vs_station_solo_si_el_que_habla_despues_es_station_con_pi_alto():
    t = spot_btn("As Kd", 0)                                      # Bender es el botón: solo hablan después las ciegas
    assert capa_con(0.8, apertura_vs_station=3.5)._tam_apertura_bb(t) == (3.5, True)
    assert capa_con(0.7, apertura_vs_station=3.5)._tam_apertura_bb(t) == (3.5, True)          # π >= 0,7
    assert capa_con(0.69, apertura_vs_station=3.5)._tam_apertura_bb(t) == (2.5, False)
    assert capa_con(0.9)._tam_apertura_bb(t) == (2.5, False)                                  # por defecto = tamano_bb: sin efecto
    # Bender sin memoria de rivales: tamaño base
    from capa1 import Capa1
    p = params(n_min=500, eps_obj=0.02)
    p["apertura"]["apertura_vs_station"] = 3.5
    assert Capa1(p, rng=random.Random(7))._tam_apertura_bb(t) == (2.5, False)


def test_apertura_vs_station_cambia_el_monto_de_la_apertura_y_del_iso():
    capa = capa_con(0.9, apertura_vs_station=3.5)
    accion, _, info = capa.decidir(spot_btn("As Kd", 0), MesaFalsa())
    assert accion == {"tipo": "raise", "monto": 350} and info["vs_station"] is True
    # el iso-raise parte del tamaño vs station: 3,5 + 1 · 2 limpers = 5,5 bb. (Con memoria el menú usa ranuras del observador: se
    # comprueba solo el tamaño calculado.)
    assert capa._tam_apertura_bb(spot_btn("As Kd", 2))[0] + 1.0 * 2 == 5.5


def test_el_que_habla_antes_no_cuenta_para_vs_station():
    """Bender en la ciega grande: ya habló todo el mundo antes (salvo nadie): no hay quien hable después."""
    t = spot_bb("As Kd")
    assert capa_con(0.9, apertura_vs_station=3.5)._tam_apertura_bb(t) == (2.5, False)
