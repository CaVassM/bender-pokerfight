"""Capa 1 · Equity por Monte Carlo contra rangos (§1.2 y §1.3 del .tex).

  e ≈ (W + Σ 1/k_j) / N          σ_e = sqrt(e(1-e)/N)

En cada simulación se SORTEA el combo de cada rival con probabilidad
proporcional a su peso w(h) (§1.3); con varios rivales se sortea un combo de
cada rango y se DESCARTA la simulación si dos combos comparten carta (solo
cuentan las aceptadas: es la distribución condicionada a que no choquen). Luego
se completa el board con cartas al azar de las que quedan. Un empate entre k
jugadores le da a Bender 1/k.

Cuándo parar (reloj adaptativo, §1.2): se revisa cada `revisar_cada`=64
simulaciones y se para si

    N >= N_min  y  (σ_e <= ε_obj   o   |e - e_ref| >= k·σ_e)      o      t >= T_max
    T_max = max(T_piso, min(T_tope, η · T_rest / D_rest)),  D_rest = 2,5 · (50 - manos jugadas)

T_piso (reloj.t_piso_s, 0,25 s) existe porque la final dura 1 hora en UNA mesa: pasados
los 360 s T_rest es <= 0 y, sin piso, T_max valdría 0 y cada decisión usaría solo 64
simulaciones. En una mesa al día (clasificatoria) el piso no actúa: η·T_rest/D_rest
es ~1,4 s al empezar y solo baja de 0,25 s si la mesa va muy atrasada.

Dos salvaguardas que el .tex no dice y que no cambian la regla: siempre se corre
al menos un bloque de 64 simulaciones (con T_max = 0 no habría ninguna estimación),
y si no se acepta ninguna simulación tras muchos intentos (rangos que no pueden
convivir) se devuelve `imposible=True` en vez de colgarse.
"""

import math
import random
import time
from bisect import bisect_right
from dataclasses import dataclass

import cartas as C
from cartas import evaluar7

MAX_INTENTOS_SIN_ACEPTAR = 5000


@dataclass
class ResultadoEquity:
    e: float                  # equity estimada (fracción del pozo)
    n: int                    # simulaciones aceptadas (N)
    sigma: float              # σ_e = sqrt(e(1-e)/N)
    tiempo_s: float           # tiempo usado
    parada: str               # "precision" | "umbral" | "tiempo" | "fijo" | "imposible"
    t_max: float = 0.0        # T_max aplicado
    e_ref: float = None       # umbral más cercano a e al parar
    intentos: int = 0         # simulaciones sorteadas (incluye las descartadas por choque)
    imposible: bool = False


def t_max_de_reloj(cfg, manos_jugadas, segundos_mesa):
    """T_max = max(T_piso, min(T_tope, η · T_rest / D_rest)) (§1.2).

    Con la mesa pasada de su tiempo (T_rest <= 0: la final, que dura 1 hora en una sola mesa) vale T_piso, no 0."""
    piso = cfg.get("t_piso_s", 0.0)
    d_rest = cfg["decisiones_por_mano"] * (cfg["manos_mesa"] - manos_jugadas)
    t_rest = cfg["t_mesa"] - segundos_mesa
    if t_rest <= 0:
        return piso
    if d_rest <= 0:
        return max(piso, cfg["t_tope"])
    return max(piso, min(cfg["t_tope"], cfg["eta"] * t_rest / d_rest))


def _preparar(mano, board, rivales):
    """Rangos vivos (sin cartas de Bender ni del board) y máscara de cartas muertas."""
    muertas = C.mascara(list(mano) + list(board))
    vivos = [r.filtrar(muertas) if (r.masks and any(m & muertas for m in r.masks)) else r for r in rivales]
    return muertas, vivos


def estimar(mano, board, rivales, cfg=None, umbrales=(), manos_jugadas=0, segundos_mesa=0.0,
            rng=None, n_fijo=None, t_max=None):
    """Equity de `mano` (2 ids) en `board` (0 a 5 ids) contra una lista de rangos.

    Con `n_fijo` corre exactamente esas simulaciones (para tests y calibración).
    Si no, usa el reloj adaptativo de `cfg` (params["reloj"]); `umbrales` son los
    e_ref candidatos (e_min de §1.6, 0,25 y 0,50 de §1.11) y `t_max` fuerza el
    tope de tiempo (si no, sale de manos_jugadas y segundos_mesa).
    """
    rng = rng or random.Random()
    rnd = rng.random
    inicio = time.perf_counter()
    muertas, vivos = _preparar(mano, board, rivales)
    if any(r.vacio() for r in vivos):
        return ResultadoEquity(0.0, 0, 1.0, 0.0, "imposible", imposible=True)

    h1, h2 = mano
    board = list(board)
    faltan = 5 - len(board)
    datos = [(r.combos, r.masks, r.acum, r.total) for r in vivos]
    n_riv = len(datos)
    if n_fijo is None:
        n_min, eps, k = cfg["n_min"], cfg["eps_obj"], cfg["k"]
        revisar = cfg["revisar_cada"]
        if t_max is None:
            t_max = t_max_de_reloj(cfg, manos_jugadas, segundos_mesa)
    else:
        revisar = 1 << 62
    umbrales = tuple(umbrales)

    aceptadas = 0
    intentos = 0
    acumulado = 0.0
    proximo_control = revisar if n_fijo is None else 0
    parada, e_ref = "fijo", None
    ev7 = evaluar7

    while True:
        intentos += 1
        usadas = muertas
        elegidos = []
        choque = False
        for combos, masks, acum, total in datos:
            i = bisect_right(acum, rnd() * total)
            if i >= len(acum):
                i = len(acum) - 1
            m = masks[i]
            if usadas & m:
                choque = True
                break
            usadas |= m
            elegidos.append(combos[i])
        if choque:
            if aceptadas == 0 and intentos >= MAX_INTENTOS_SIN_ACEPTAR:
                return ResultadoEquity(0.0, 0, 1.0, time.perf_counter() - inicio, "imposible",
                                       intentos=intentos, imposible=True)
            continue

        completo = board
        if faltan:
            completo = board[:]
            for _ in range(faltan):
                c = int(rnd() * 52)
                while (usadas >> c) & 1:
                    c = int(rnd() * 52)
                usadas |= 1 << c
                completo.append(c)

        mio = ev7(h1, h2, *completo)
        empatados = 0
        perdio = False
        for a, b in elegidos:
            r = ev7(a, b, *completo)
            if r < mio:
                perdio = True
                break
            if r == mio:
                empatados += 1
        if not perdio:
            acumulado += 1.0 / (1 + empatados)
        aceptadas += 1

        if n_fijo is not None:
            if aceptadas >= n_fijo:
                break
            continue

        if aceptadas >= proximo_control:
            proximo_control += revisar
            e = acumulado / aceptadas
            sigma = math.sqrt(max(e * (1 - e), 1e-12) / aceptadas)
            if aceptadas >= n_min:
                if umbrales:
                    e_ref = min(umbrales, key=lambda u: abs(e - u))
                    if abs(e - e_ref) >= k * sigma:
                        parada = "umbral"
                        break
                if sigma <= eps:
                    parada = "precision"
                    break
            if time.perf_counter() - inicio >= t_max:
                parada = "tiempo"
                break

    e = acumulado / aceptadas
    sigma = math.sqrt(max(e * (1 - e), 0.0) / aceptadas)
    if umbrales and e_ref is None:
        e_ref = min(umbrales, key=lambda u: abs(e - u))
    return ResultadoEquity(e, aceptadas, sigma, time.perf_counter() - inicio, parada,
                           t_max=(t_max if n_fijo is None else 0.0), e_ref=e_ref, intentos=intentos)
