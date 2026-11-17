"""Pruebas del motor (paso 2): evaluador, combos y bloqueadores, rangos, equity
contra los valores del prompt (±1,5 puntos), reloj adaptativo y categorías."""

import random

import pytest

import cartas as C
import rangos as R
from equity import estimar, t_max_de_reloj
from params import cargar_params

RELOJ = cargar_params()["reloj"]
TOL = 0.015


def cs(texto):
    return C.cartas_de_texto(texto)


def equity(mano, board, rivales, n=60_000, semilla=1):
    return estimar(cs(mano), cs(board), rivales, n_fijo=n, rng=random.Random(semilla)).e


# --- Evaluador ------------------------------------------------------------------------------

def test_clases_y_orden_del_evaluador():
    def rank(t):
        return C.evaluar(cs(t))
    royal = rank("As Ks Qs Js Ts 2c 3d")
    poker = rank("9s 9h 9d 9c Ks 2c 3d")
    full = rank("9s 9h 9d Kc Ks 2c 3d")
    color = rank("As 9s 7s 4s 2s Kc Kd")
    escalera = rank("9s 8h 7d 6c 5s Ac Ad")
    trio = rank("9s 9h 9d Kc Qs 2c 3d")
    doble = rank("9s 9h Kd Kc Qs 2c 3d")
    par = rank("9s 9h Ad Kc Qs 2c 3d")
    alta = rank("As Kh Qd Jc 9s 2c 3d")
    orden = [royal, poker, full, color, escalera, trio, doble, par, alta]
    assert orden == sorted(orden) and len(set(orden)) == 9          # menor = más fuerte
    assert [C.clase_de_rank(r) for r in orden] == list(range(9)) or C.clase_de_rank(royal) == 0
    assert [C.clase_de_rank(r) for r in orden[1:]] == [1, 2, 3, 4, 5, 6, 7, 8]


def test_rueda_pierde_contra_escalera_a_seis_y_empates_exactos():
    rueda = C.evaluar(cs("As 2h 3d 4c 5s Kc Kd"))
    seis = C.evaluar(cs("2s 3h 4d 5c 6s Kc Kd"))
    assert C.clase_de_rank(rueda) == C.ESCALERA and seis < rueda
    # El kicker no desempata la escalera, y los palos tampoco
    assert C.evaluar(cs("9s 8h 7d 6c 5s Ac Ad")) == C.evaluar(cs("9c 8d 7h 6s 5c 2c 2d"))


def test_evaluador_coincide_con_el_de_la_mesa():
    """Contraste con pkg/poker (el que decide los showdowns reales)."""
    import os
    import shutil
    import subprocess
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    go = shutil.which("go") or r"C:\Program Files\Go\bin\go.exe"
    if not os.path.exists(go) and not shutil.which("go"):
        pytest.skip("Go no está instalado")

    rng = random.Random(7)
    manos = [rng.sample(range(52), 7) for _ in range(120_000)]
    for cima in range(5, 15):                                          # escaleras de todas las alturas
        for _ in range(300):
            rangos = [cima - i for i in range(5)] if cima > 5 else [5, 4, 3, 2, 14]
            base = [C.carta(r, rng.randrange(4)) for r in rangos]
            resto = rng.sample([c for c in range(52) if c not in base], 2)
            manos.append(base + resto)
    for _ in range(3000):                                              # colores y escaleras de color
        palo = rng.randrange(4)
        manos.append([C.carta(r, palo) for r in rng.sample(range(2, 15), 7)])
    entrada = "\n".join(" ".join(map(str, m)) for m in manos) + "\n"
    out = subprocess.run([go, "run", "./bender/pruebas/xcheck_evaluador"], input=entrada, capture_output=True,
                         text=True, cwd=raiz, timeout=300)
    assert out.returncode == 0, out.stderr
    puntajes = [int(x) for x in out.stdout.split()]
    assert len(puntajes) == len(manos) and min(puntajes) >= 0

    # Mismo orden y mismos empates: cada rank de phevaluator corresponde a un solo
    # Puntaje de la mesa, y a mayor rank (más débil) menor Puntaje.
    por_rank = {}
    for m, p in zip(manos, puntajes):
        por_rank.setdefault(C.evaluar(m), set()).add(p)
    assert all(len(v) == 1 for v in por_rank.values()), "una misma jugada tiene dos puntajes en la mesa"
    ordenados = [next(iter(por_rank[r])) for r in sorted(por_rank)]
    assert all(a > b for a, b in zip(ordenados, ordenados[1:])), "el orden de fuerza no coincide con el de la mesa"


def test_velocidad_del_evaluador_supera_la_meta():
    import time
    rng = random.Random(3)
    manos = [rng.sample(range(52), 7) for _ in range(100_000)]
    t = time.perf_counter()
    for m in manos:
        C.evaluar7(*m)
    assert len(manos) / (time.perf_counter() - t) > 300_000


# --- Combos, bloqueadores y rangos ---------------------------------------------------------------

def test_combos_por_clase_y_total():
    assert (R.n_combos("AA"), R.n_combos("AKs"), R.n_combos("AKo")) == (6, 4, 12)
    assert sum(R.n_combos(c) for c in R.CLASES_169) == 1326
    assert len(R.CLASES_169) == 169
    assert all(len(R.combos_de_clase(c)) == R.n_combos(c) for c in R.CLASES_169)


def test_bloqueadores_con_AsJh():
    muertas = C.mascara(cs("As Jh"))
    r = R.rango_de_texto("AA, AKs, AKo", muertas)
    cuenta = r.conteo_por_clase()
    assert cuenta == {"AA": 3, "AKs": 3, "AKo": 9}


def test_rango_QQmas_AK_tiene_27_combos_vivos_con_AsJh():
    muertas = C.mascara(cs("As Jh"))
    r = R.rango_de_texto("QQ+, AK", muertas)
    assert len(r) == 27
    assert R.clases_de_texto("QQ+, AK") == ["QQ", "KK", "AA", "AKs", "AKo"]


def test_notacion_de_rangos():
    assert R.clases_de_texto("ATs+") == ["ATs", "AJs", "AQs", "AKs"]
    assert R.clases_de_texto("77-99") == ["77", "88", "99"]
    assert R.clases_de_texto("A2s-A4s") == ["A2s", "A3s", "A4s"]
    with pytest.raises(ValueError):
        R.clases_de_texto("XYZ")


def test_top_pct_es_monotono_y_cubre_todo():
    n = [sum(R.n_combos(c) for c in R.clases_top(p)) for p in (5, 14.3, 25, 43.3, 70, 100)]
    assert n == sorted(n) and n[-1] == 1326
    assert R.clases_top(4)[:3] == ["AA", "KK", "QQ"]
    # Los porcentajes del .tex caen cerca de un borde de clase (±0,5 puntos): ver nota del reporte.
    for pct in (14.3, 18.9, 25.5, 43.3, 33.0, 70.0, 56.6, 38.5):
        combos = sum(R.n_combos(c) for c in R.clases_top(pct))
        assert abs(combos / 1326 * 100 - pct) < 0.6


def test_ranking_extremos():
    orden = R.cargar_rank169()["orden"]
    assert orden[:5] == ["AA", "KK", "QQ", "JJ", "TT"]
    assert orden[-1] == "32o" and orden[-2] in ("42o", "72o", "32s", "52o", "62o")


def test_reajuste_bayes_con_piso():
    r = R.rango_de_clases(["AA", "72o"])
    nuevo = r.reajustar(lambda a, b: 1.0 if R.clase_de_combo(a, b) == "AA" else 0.0, piso=0.02)
    por = nuevo.peso_total_por_clase()
    assert por["72o"] > 0 and por["AA"] > 20 * por["72o"] * 0.9           # el piso evita el cero
    assert abs(nuevo.total - 1.0) < 1e-9


# --- Equity contra los valores del prompt (±1,5 puntos) ----------------------------------------

def test_AA_contra_mano_al_azar_85():
    muertas = C.mascara(cs("As Ah"))
    assert abs(equity("As Ah", "", [R.rango_alazar(muertas)]) - 0.85) < TOL


def test_AsJh_contra_mano_al_azar_63_7():
    muertas = C.mascara(cs("As Jh"))
    assert abs(equity("As Jh", "", [R.rango_alazar(muertas)]) - 0.637) < TOL


def test_AsJh_contra_QQmas_AK_25():
    muertas = C.mascara(cs("As Jh"))
    rival = R.rango_de_texto("QQ+, AK", muertas)
    assert len(rival) == 27
    assert abs(equity("As Jh", "", [rival], n=100_000) - 0.25) < TOL


def test_AA_multiway_contra_cuatro_manos_al_azar():
    muertas = C.mascara(cs("As Ah"))
    e = equity("As Ah", "", [R.rango_alazar(muertas) for _ in range(4)], n=60_000)
    assert abs(e - 0.559) < TOL                                           # valor de tablas conocidas


def test_empates_cuentan_1_sobre_k():
    board = "As Ks Qs Js Ts"                                               # escalera real en el board: todos empatan
    muertas = C.mascara(cs("2c 3d " + board))
    r = R.rango_alazar(muertas)
    assert abs(equity("2c 3d", board, [r], n=2000) - 0.5) < 1e-9
    assert abs(equity("2c 3d", board, [r, r], n=2000) - 1 / 3) < 1e-9


def test_rangos_imposibles_no_cuelgan():
    muertas = C.mascara(cs("As Ah"))
    aa = R.rango_de_texto("AA", muertas)                                   # queda un solo combo vivo
    res = estimar(cs("As Ah"), [], [aa, aa], n_fijo=100, rng=random.Random(1))
    assert res.imposible and res.parada == "imposible"


def test_equity_en_flop_turn_y_river_es_coherente():
    # Color hecho en el river contra un rango amplio: gana casi siempre
    board = "2s 7s Js 9d Kc"
    muertas = C.mascara(cs("As Ts " + board))
    e = equity("As Ts", board, [R.rango_top(40, muertas)], n=8000)
    assert e > 0.85


# --- Reloj adaptativo (§1.2) ---------------------------------------------------------------------

def test_t_max_del_reloj():
    assert abs(t_max_de_reloj(RELOJ, 0, 0.0) - 1.44) < 1e-9               # min(1,5, 0,5·360/125)
    assert t_max_de_reloj(RELOJ, 49, 343.0) == RELOJ["t_tope"]            # 0,5·17/2,5 = 3,4 > 1,5
    assert t_max_de_reloj(RELOJ, 25, 340.0) < 0.5                         # va atrasado: se achica
    assert t_max_de_reloj(RELOJ, 10, 400.0) == RELOJ["t_piso_s"]          # se acabó el tiempo de la mesa: piso, no 0
    assert t_max_de_reloj(RELOJ, 100, 400.0) == RELOJ["t_piso_s"]         # la final: más de 50 manos y más de 360 s
    assert t_max_de_reloj(RELOJ, 100, 300.0) == RELOJ["t_tope"]           # más de 50 manos con tiempo: el tope de siempre
    assert t_max_de_reloj(RELOJ, 49, 359.9) == RELOJ["t_piso_s"]          # quedan 0,1 s: 0,5·0,1/2,5 = 0,02 < piso
    # en una mesa al día el piso no actúa
    for m in range(0, 50):
        al_dia = t_max_de_reloj(RELOJ, m, m * 7.2)
        assert al_dia == min(RELOJ["t_tope"], RELOJ["eta"] * (RELOJ["t_mesa"] - m * 7.2) / (RELOJ["decisiones_por_mano"] * (50 - m)))
        assert al_dia > RELOJ["t_piso_s"]


def test_mesa_de_la_final_sigue_simulando_bien():
    """(a) Mesa a los 400 s de iniciada (y más de 50 manos): la equity de un spot normal llega a N >= 2000, no a 64."""
    muertas = C.mascara(cs("Ks Qs"))
    rangos = [R.rango_top(30, muertas)]
    res = estimar(cs("Ks Qs"), cs("Js 7d 2c"), rangos, RELOJ, umbrales=(0.25, 0.5), manos_jugadas=120, segundos_mesa=400.0,
                  rng=random.Random(3))
    assert res.t_max == RELOJ["t_piso_s"]
    assert res.n >= RELOJ["n_min"], res.n
    assert res.tiempo_s < 1.0


def test_para_por_umbral_cuando_esta_lejos():
    muertas = C.mascara(cs("As Ah"))
    res = estimar(cs("As Ah"), [], [R.rango_alazar(muertas)], RELOJ, umbrales=(0.5,), rng=random.Random(1), t_max=1.5)
    assert res.parada == "umbral" and RELOJ["n_min"] <= res.n <= RELOJ["n_min"] + 2 * RELOJ["revisar_cada"] and res.e_ref == 0.5


def test_para_por_precision_cuando_el_umbral_esta_cerca():
    muertas = C.mascara(cs("7s 6s"))
    res = estimar(cs("7s 6s"), [], [R.rango_alazar(muertas)], RELOJ, umbrales=(0.5,), rng=random.Random(1), t_max=5.0)
    assert res.parada in ("precision", "umbral") and res.sigma <= RELOJ["eps_obj"] + 1e-9 or res.parada == "umbral"
    assert res.tiempo_s < 2.0


def test_con_tiempo_agotado_corre_un_bloque_minimo():
    muertas = C.mascara(cs("As Ah"))
    res = estimar(cs("As Ah"), [], [R.rango_alazar(muertas)], RELOJ, rng=random.Random(1), t_max=0.0)
    assert res.parada == "tiempo" and res.n == RELOJ["revisar_cada"]


# --- Categorías de §2.2 ----------------------------------------------------------------------------

@pytest.mark.parametrize("mano,board,esperada", [
    ("As Ah", "Jd 7c 2s", R.FUERTE),        # overpair
    ("Js Th", "Jd 7c 2s", R.FUERTE),        # top pair
    ("7h 7s", "Jd 7c 2s", R.FUERTE),        # trío (set)
    ("Jh 7h", "Jd 7c 2s", R.FUERTE),        # dos pares con las dos cartas
    ("Kd Qd", "Jd 7d 2s", R.PROYECTO),      # proyecto de color (9 outs)
    ("Th 9s", "Jd 8c 2s", R.PROYECTO),      # escalera abierta (8 outs)
    ("8h 8s", "Jd 7c 2s", R.MEDIA),         # pareja de bolsillo bajo la carta alta
    ("7h 6s", "Jd 7c 2s", R.MEDIA),         # segunda pareja
    ("2h 3s", "Jd 7c 2s", R.MEDIA),         # tercera pareja
    ("As Ks", "Jd 7c 2s", R.AIRE),          # dos overcards sin nada
    ("Th 9s", "Jd 7c 2s", R.AIRE),          # solo gutshot... ni eso
    ("Qh Ts", "Jd 8c 2s", R.AIRE),          # gutshot (solo el 9, 4 outs) cuenta como aire
    ("Qh Ts", "Jd 9c 2s", R.PROYECTO),      # Q-J-T-9: escalera abierta (8 o K), 8 outs
    ("As Ks", "Qd Jd Th", R.FUERTE),        # escalera hecha
    ("Ah 3h", "Kh 9h 2h", R.FUERTE),        # color hecho
    ("Kh Qs", "Ad Ac 5s", R.AIRE),          # el board tiene la pareja; Bender no tiene nada
    ("9h 9s", "Kd Kc 4s", R.MEDIA),         # dos pares con pareja de bolsillo bajo el board
])
def test_categorias(mano, board, esperada):
    assert R.categoria_mano(cs(mano), cs(board)) == esperada


def test_proyecto_en_el_turn_y_aire_en_el_river():
    assert R.categoria_mano(cs("Kd Qd"), cs("Jd 7d 2s 4c")) == R.PROYECTO
    assert R.categoria_mano(cs("Kd Qd"), cs("Jd 7d 2s 4c 9h")) == R.AIRE      # en el river ya no hay proyecto
