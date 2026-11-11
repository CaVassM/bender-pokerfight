"""Capa 1 · Modelo de población: qué rango le suponemos a cada rival SIN memoria.

La Capa 1 necesita rangos para calcular e (equity contra el rango del rival) y
e' (equity si le pagan). Sin datos del rival se usa el "rival promedio" (prior de
población); la Capa 2 (rivales.py) reemplaza estos supuestos por la memoria de
cada ID, pero usa exactamente las mismas piezas:

  - c(x) de población (§1.7);
  - rango preflop de quien entra (§1.5 por posición, §2.8 para quien paga);
  - reajuste Bayes del rango con cada acción postflop (§2.1) usando las
    plantillas por categoría (§2.2): P(acción | categoría de la mano);
  - c = Σ w·P(sigue|h) / Σ w (§2.1) y el rango de los que pagan.

Todo se recalcula desde el historial de la mano en cada decisión (sin estado), así
que una reconexión a mitad de mano no rompe nada.
"""

import random

import cartas as C
import rangos as R

APUESTAS = ("bet", "raise", "allin")
CALLES = ("preflop", "flop", "turn", "river")
CARTAS_DE_CALLE = {"flop": 3, "turn": 4, "river": 5}


# --- §1.7 Fold equity de población --------------------------------------------------------

def c_poblacion(x, ya_puso, p):
    """c(x) = 0,65 / (1 + 0,55 x), +0,12 si el rival ya puso fichas en esta ronda; tope 0,9."""
    c = p["a"] / (1.0 + p["b"] * x)
    if ya_puso:
        c += p["extra_ya_puso"]
    return min(p["tope"], c)


# --- §2.2 Plantillas ----------------------------------------------------------------------

def _fila(params, tipo):
    return params["plantillas"]["promedio" if tipo == "tag" else tipo]


def plantilla_mezcla(pi, params):
    """P(acción | categoría) mezclando los tipos con la creencia π (§2.4):
    {categoría: (retira, paga, sube)}. Con pi={'tag': 1} es la fila 'Promedio'."""
    out = {}
    for cat in (R.FUERTE, R.MEDIA, R.PROYECTO, R.AIRE):
        v = [0.0, 0.0, 0.0]
        for tipo, w in pi.items():
            fila = _fila(params, tipo)[cat]
            for i in range(3):
                v[i] += w * fila[i]
        out[cat] = tuple(v)
    return out


def prob_apuesta(pi, params):
    """P(apuesta | categoría) cuando nadie apostó (§2.2): fuerte .65, media .35,
    proyecto .45, aire .25 para el promedio; nit ×0,7, station ×0,6, maníaco ×1,5
    (tope .95); aleatorio .50 en todo."""
    pa = params["prob_apuesta"]
    por_tipo = pa.get("por_tipo", {})
    out = {}
    for cat in (R.FUERTE, R.MEDIA, R.PROYECTO, R.AIRE):
        s = 0.0
        for tipo, w in pi.items():
            if tipo in por_tipo:                       # tipos calibrados con los bots del kit (TAG, station)
                s += w * por_tipo[tipo][cat]
            elif tipo == "aleatorio":
                s += w * pa["aleatorio"]
            else:
                s += w * min(pa["tope"], pa["base"][cat] * pa["mult"].get(tipo, 1.0))
        out[cat] = s
    return out


def c_de_rango_postflop(c_medio, x, ya_puso, p):
    """§2.1: la plantilla está calibrada para x≈1/2; para otro tamaño se escala con el modelo de
    población: c(x) = c_{1/2} · c_pob(x) / c_pob(1/2)."""
    escala = c_poblacion(x, ya_puso, p) / c_poblacion(0.5, ya_puso, p)
    return min(0.95, c_medio * escala)


def c_de_rango_preflop(rango, x, ya_puso, p):
    """c preflop a partir del rango del rival (§3.3: θ_base de c_i sale del rango).

    El rival sigue con las manos que están dentro del top c_pob(x) % de TODAS las manos. Con un
    rango ancho (mano al azar) eso es c_pob(x), igual que en §1.7; con un rango estrecho (quien
    acaba de subir o re-subir) casi todo el rango está dentro del umbral y c → 1: el que re-subió
    no se retira porque le subamos otra vez. Sin esto, Bender "farolea" re-subidas contra rangos
    que no se retiran."""
    if rango.total <= 0:
        return c_poblacion(x, ya_puso, p)
    top = set(R.clases_top(100.0 * c_poblacion(x, ya_puso, p)))
    dentro = sum(w for clase, w in rango.peso_total_por_clase().items() if clase in top)
    return min(0.98, dentro / rango.total)


N_FUERZA = 96        # repartos por board (flop y turn) para estimar la equity de CUALQUIER combo contra una mano al azar


class CacheCategorias:
    """Memoriza, por (combo, board), la categoría de la mano (categoria_mano recorre las cartas que
    faltan para contar outs y es lo más caro del modelo) y su fuerza (equity contra una mano al azar)."""

    def __init__(self):
        self._d = {}
        self._f = {}
        self._m = {}          # board -> repartos compartidos para estimar la fuerza de todos los combos

    def de(self, combo, board):
        clave = (combo, board)
        v = self._d.get(clave)
        if v is None:
            v = self._d[clave] = R.categoria_mano(combo, board)
        return v

    def fuerza(self, combo, board):
        """Fuerza del combo en ese board = su equity contra UNA MANO AL AZAR (§1.9: ordena el rango que
        paga; el rival no conoce las cartas de Bender; solo depende del combo y del board).

        River: exacta, monótona en el rank de la mano. Flop y turn: Monte Carlo sobre repartos
        compartidos por board (ver `_repartos`). Se calcula una vez por (combo, board) y se reutiliza
        para todos los rivales, tamaños y decisiones de esa calle."""
        clave = (combo, board)
        v = self._f.get(clave)
        if v is None:
            if len(board) == 5:
                v = 1.0 - C.evaluar7(combo[0], combo[1], *board) / 7463.0
            else:
                v = self._fuerza_mc(combo, board)
            self._f[clave] = v
        return v

    def _repartos(self, board):
        """Repartos al azar compartidos para estimar la equity de TODOS los combos de un board: cada uno
        es (máscara de las cartas usadas, board completo, rank de la mano rival). Se sortean una vez por
        board (semilla fija: reproducible). Un combo usa los repartos que no chocan con sus cartas:
        condicionar así deja una distribución uniforme sobre el resto de la baraja, o sea el mismo
        estimador de siempre, pero cada combo cuesta 1 evaluación por reparto (antes 2 más el sorteo)."""
        rep = self._m.get(board)
        if rep is None:
            rng = random.Random(hash(board) & 0xFFFFFFFF)
            en_board = set(board)
            mazo = [c for c in C.TODAS if c not in en_board]
            faltan = 5 - len(board)
            rep = []
            for _ in range(N_FUERZA):
                extra = rng.sample(mazo, faltan + 2)
                completo = list(board) + extra[:faltan]
                rep.append((C.mascara(extra), tuple(completo), C.evaluar7(extra[faltan], extra[faltan + 1], *completo)))
            self._m[board] = rep
        return rep

    def _fuerza_mc(self, combo, board):
        a, b = combo
        m = (1 << a) | (1 << b)
        ev7, acum, n = C.evaluar7, 0.0, 0
        for mask, completo, rank_rival in self._repartos(board):
            if mask & m:
                continue
            r = ev7(a, b, *completo)
            acum += 1.0 if r < rank_rival else (0.5 if r == rank_rival else 0.0)
            n += 1
        return acum / n if n else 0.5


def rango_de_pago_por_fuerza(rango, board, frac, cache):
    """R_paga(x) postflop (§1.9): la fracción `frac` = c(x) MÁS FUERTE del rango del rival, ordenada por la
    fuerza de cada combo en ese board (su equity contra una mano al azar)."""
    if frac >= 1.0 or rango.vacio():
        return rango
    board = tuple(sorted(board))
    items = sorted(zip(rango.combos, rango.pesos), key=lambda it: -cache.fuerza(it[0], board))
    meta = frac * rango.total
    acumulado, out = 0.0, []
    for combo, w in items:
        if acumulado >= meta:
            break
        usar = min(w, meta - acumulado)
        out.append((combo, usar))
        acumulado += usar
    return R.Rango(out) if out else rango


def c_sigue(rango, board, plantilla, cache):
    """c = Σ w·P(sigue|h) / Σ w (§2.1): probabilidad de que el rival siga ante una apuesta."""
    board = tuple(sorted(board))
    s = 0.0
    for combo, w in zip(rango.combos, rango.pesos):
        _, paga, sube = plantilla[cache.de(combo, board)]
        s += w * (paga + sube)
    return s / rango.total if rango.total > 0 else 0.0


def reajustar(rango, board, tabla_cat, cache, piso):
    """Bayes con pesos (§2.1) con P(a|h) = tabla_cat[categoría de h en el board]."""
    board = tuple(sorted(board))
    return rango.reajustar(lambda a, b: tabla_cat[cache.de((a, b), board)], piso)


def rango_de_pago(rango, board, plantilla, cache, piso):
    """Rango del rival DESPUÉS de pagar una apuesta: w·P(paga|h) (§2.1)."""
    return reajustar(rango, board, {cat: v[1] for cat, v in plantilla.items()}, cache, piso)


# --- Rangos preflop ---------------------------------------------------------------------------

def clave_posicion(posicion):
    return "BTN_SB_HU" if posicion == "BTN/SB" else posicion


def pct_de_posicion(posicion, params):
    """Top % con el que la población abre desde esa posición (§1.5)."""
    tabla = params["apertura"]["top_pos"]
    return tabla.get(clave_posicion(posicion), params["capa1"]["pct_bb_sin_posicion"])


def rango_preflop(n_subidas, n_pagos, posicion, params):
    """Rango inicial de un rival según lo que hizo preflop.

      - subió: top % de población de su posición (§1.5, con ρ=0 en la Capa 1); cada
        re-subida lo estrecha (`estrecha_por_subida`, con piso `min_pct_rango`);
      - solo pagó: w=1 para top(VPIP) sin top(PFR) y 0,3 para top(PFR) (§2.8);
      - no hizo nada voluntario (ciega que pasó, o aún no actuó): mano al azar.
    """
    c1 = params["capa1"]
    pct_pfr = pct_de_posicion(posicion, params)
    if n_subidas >= 1:
        pct = max(c1["min_pct_rango"], pct_pfr * (c1["estrecha_por_subida"] ** (n_subidas - 1)))
        return R.rango_top(pct)
    if n_pagos >= 1:
        vpip = 100.0 * params["beta"]["m"]["vpip"]
        top_pfr = set(R.clases_top(pct_pfr))
        pesos = {}
        for clase in R.clases_top(max(vpip, pct_pfr)):
            pesos[clase] = params["preflop_rango"]["peso_top_pfr_si_paga"] if clase in top_pfr else 1.0
        return R.rango_de_clases(pesos)
    return R.rango_alazar()


def top_fraccion(rango, frac):
    """Las mejores manos del rango (por el ranking de 169 clases) que suman `frac`
    de su peso. Sirve de rango de pago preflop: el rival que paga con probabilidad
    c lo hace con su fracción c más fuerte."""
    if frac >= 1.0:
        return rango
    orden = {c: i for i, c in enumerate(R.cargar_rank169()["orden"])}
    items = sorted(zip(rango.combos, rango.pesos), key=lambda it: orden[R.clase_de_combo(*it[0])])
    meta = frac * rango.total
    acumulado, out = 0.0, []
    for combo, w in items:
        if acumulado >= meta:
            break
        usar = min(w, meta - acumulado)
        out.append((combo, usar))
        acumulado += usar
    return R.Rango(out) if out else rango


# --- Historial -> eventos por rival --------------------------------------------------------------

def eventos(historial):
    """[(id, etapa, tipo, enfrentaba_apuesta)] en orden. `enfrentaba_apuesta` es
    True si ya hubo un bet/raise/all-in en esa calle antes de la acción."""
    hubo = {}
    out = []
    for h in historial:
        etapa, tipo = h.get("etapa"), (h.get("accion") or {}).get("tipo")
        out.append((h.get("id_jugador"), etapa, tipo, hubo.get(etapa, False)))
        if tipo in APUESTAS:
            hubo[etapa] = True
    return out


def tabla_de_accion(tipo, enfrentaba, plantilla, pa):
    """P(acción observada | categoría) para el reajuste, o None si no informa
    (retirarse saca al rival de la mano)."""
    if tipo == "fold":
        return None
    if not enfrentaba:
        if tipo == "check":
            return {cat: 1.0 - pa[cat] for cat in pa}
        if tipo in APUESTAS:
            return dict(pa)
        return None
    if tipo == "call":
        return {cat: v[1] for cat, v in plantilla.items()}
    if tipo in ("raise", "allin", "bet"):
        return {cat: v[2] for cat, v in plantilla.items()}
    return None


def rango_de_rival(rival_id, posicion, eventos_todos, board, mano_bender, params, cache, pi=None):
    """Rango vivo de un rival en la mano actual: preflop según lo que hizo y, calle
    por calle, reajustado con sus acciones (§2.1) y sin los combos bloqueados."""
    pi = pi or params["capa1"]["pi_defecto"]
    plantilla = plantilla_mezcla(pi, params)
    pa = prob_apuesta(pi, params)
    piso = params["rango"]["piso"]

    propios = [e for e in eventos_todos if e[0] == rival_id]
    n_sub = sum(1 for e in propios if e[1] == "preflop" and e[2] in APUESTAS)
    n_pag = sum(1 for e in propios if e[1] == "preflop" and e[2] == "call")
    r = rango_preflop(n_sub, n_pag, posicion, params)

    for calle in ("flop", "turn", "river"):
        n = CARTAS_DE_CALLE[calle]
        if len(board) < n:
            break
        board_calle = board[:n]
        r = r.filtrar(C.mascara(list(mano_bender) + list(board_calle)))
        for _, etapa, tipo, enfrentaba in propios:
            if etapa != calle:
                continue
            tabla = tabla_de_accion(tipo, enfrentaba, plantilla, pa)
            if tabla is not None and not r.vacio():
                r = reajustar(r, board_calle, tabla, cache, piso)
    return r.filtrar(C.mascara(list(mano_bender) + list(board)))
