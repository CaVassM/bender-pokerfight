"""Pruebas del modelo de población (poblacion.py): c(x), plantillas, rangos preflop,
reajuste por acciones y el ejemplo numérico de §2.1."""

import pytest

import cartas as C
import poblacion as POB
import rangos as R
from estado import Jugador
from params import cargar_params

from params import PLANTILLAS_TEX, PROB_APUESTA_TEX  # noqa: E402

PC = cargar_params()                      # parámetros vigentes (plantillas CALIBRADAS)
# Los ejemplos numéricos del .tex (c = 0,37, "aire 66 % → 19 %"...) están escritos con las plantillas
# PROVISIONALES: estas pruebas usan esos valores, que se conservan en params.PLANTILLAS_TEX.
P = cargar_params()
P["plantillas"].update({k: v for k, v in PLANTILLAS_TEX.items()})
P["prob_apuesta"]["base"] = dict(PROB_APUESTA_TEX)
P["prob_apuesta"]["por_tipo"] = {}


def test_las_plantillas_calibradas_son_distribuciones_y_reflejan_a_los_bots_del_kit():
    for tipo in ("promedio", "station"):
        for cat, fila in PC["plantillas"][tipo].items():
            assert abs(sum(fila) - 1.0) < 0.01, (tipo, cat, fila)
    tag = PC["plantillas"]["promedio"]
    assert tag["aire"][2] < 0.02                                   # el TAG casi nunca sube con aire
    assert tag["fuerte"][0] < tag["proyecto"][0] < tag["aire"][0]  # se retira más cuanto más débil
    pa = POB.prob_apuesta({"tag": 1.0}, PC)
    assert pa["fuerte"] > 0.8 and pa["aire"] < 0.3
    st = POB.prob_apuesta({"station": 1.0}, PC)
    assert max(st.values()) < 0.05                                 # el conservador nunca apuesta
    # El station medido se retira igual con cualquier mano (paga barato, no mira sus cartas)
    rets = [PC["plantillas"]["station"][c][0] for c in ("fuerte", "media", "proyecto", "aire")]
    assert max(rets) - min(rets) < 0.05


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

# Las 48 clases (340 combos) del top 25 % del ejemplo, tal como las dio el equipo. Lista FIJA: no
# depende de nuestro ranking de 169 clases.
TOP25_DEL_TEX = ("AA KK QQ JJ TT 99 88 AKs 77 AQs AKo AJs ATs AQo AJo KQs A9s 66 KJs ATo A8s KTs KQo A7s 55 QJs KJo "
                 "A9o K9s A5s A8o A6s KTo QTs A4s A7o A3s K8s QJo JTs A6o K7s A5o K9o A2s Q9s QTo A4o").split()


def test_la_lista_del_ejemplo_tiene_48_clases_y_340_combos():
    assert len(TOP25_DEL_TEX) == 48 and len(set(TOP25_DEL_TEX)) == 48
    assert sum(R.n_combos(c) for c in TOP25_DEL_TEX) == 340


def ejemplo():
    mano, board = cs("As Jh"), cs("Jd 7c 2s")
    rango = R.rango_de_clases(TOP25_DEL_TEX, C.mascara(mano + board))
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


def test_ejemplo_2_1_medios_y_aire_dentro_de_5_combos():
    _, _, _, _, por_cat = ejemplo()
    assert abs(por_cat.get("media", 0) - 45) <= 5
    assert abs(por_cat.get("aire", 0) - 171) <= 5


def test_e_prima_postflop_ordena_por_fuerza_contra_mano_al_azar_y_no_por_la_mano_de_bender():
    """§1.9: R_paga(x) = fracción c(x) más fuerte del rango, ordenada por la equity de cada combo
    contra una mano al azar en ese board."""
    mano, board, rango, cache, _ = ejemplo()
    b = tuple(sorted(board))
    paga = POB.rango_de_pago_por_fuerza(rango, board, 0.25, cache)
    assert abs(paga.total - 0.25 * rango.total) < 1e-6
    fuerzas = {c: cache.fuerza(c, b) for c in rango.combos}
    corte = min(fuerzas[c] for c in paga.combos)
    fuera = [fuerzas[c] for c in rango.combos if c not in set(paga.combos)]
    assert max(fuera) <= corte + 1e-9                    # todo lo que paga es más fuerte que lo que no paga
    # el trío de sietes y los reyes/reinas arriba; el aire con A alto, abajo
    clases_paga = paga.conteo_por_clase()
    assert "AA" in clases_paga and "KK" in clases_paga and "AKs" not in clases_paga
    # River: ordenado exactamente por el rank del evaluador
    river = cs("Jd 7c 2s 9h 4d")
    rb = tuple(sorted(river))
    c1, c2 = tuple(sorted(cs("Ad Ah"))), tuple(sorted(cs("5s 3s")))
    assert cache.fuerza(c1, rb) > cache.fuerza(c2, rb)


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
