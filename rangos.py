"""Capa 1 · Rangos, combos y categorías de mano.

Un *rango* es un conjunto de combos de dos cartas (combo = h en el .tex) con un
peso w(h) entre 0 y 1 (§1.3, §2.1). Aquí viven:

  - las 169 clases de mano (AA, AKs, AKo...) y cuántos combos tiene cada una:
    6 las parejas, 4 las suited, 12 las offsuit (§1.1);
  - combos *vivos*: se borran los que usan una carta muerta (la de Bender o el
    board), así que los bloqueadores salen solos (§1.1);
  - el ranking de las 169 clases por equity contra una mano al azar
    (bender/datos/rank169.json, lo genera `generar_rank169`) y `top(pct)` (§1.5);
  - la categoría de una mano en un board: fuerte / media / proyecto / aire (§2.2).
"""

import bisect
import json
import os
import re

import cartas as C

DATOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")
RUTA_RANK169 = os.path.join(DATOS, "rank169.json")
SIMB = "23456789TJQKA"


# --- Las 169 clases --------------------------------------------------------------------

def etiqueta(r1, r2, tipo):
    """(14, 13, 's') -> 'AKs'. Las parejas no llevan sufijo."""
    return f"{SIMB[r1 - 2]}{SIMB[r2 - 2]}{'' if tipo == 'p' else tipo}"


def _clases():
    out = []
    for r1 in range(14, 1, -1):
        for r2 in range(r1, 1, -1):
            if r1 == r2:
                out.append((r1, r2, "p"))
            else:
                out.append((r1, r2, "s"))
                out.append((r1, r2, "o"))
    return out


CLASES_169 = [etiqueta(*c) for c in _clases()]
_CLASE_DE_ETIQUETA = {etiqueta(*c): c for c in _clases()}


def n_combos(clase):
    """6, 4 o 12 según sea pareja, suited u offsuit."""
    return {"p": 6, "s": 4, "o": 12}[_CLASE_DE_ETIQUETA[clase][2]]


def combos_de_clase(clase):
    """Todos los combos (a, b) con a < b de una clase, como ids de carta."""
    r1, r2, tipo = _CLASE_DE_ETIQUETA[clase]
    out = []
    if tipo == "p":
        for p1 in range(4):
            for p2 in range(p1 + 1, 4):
                out.append(tuple(sorted((C.carta(r1, p1), C.carta(r1, p2)))))
    elif tipo == "s":
        for p in range(4):
            out.append(tuple(sorted((C.carta(r1, p), C.carta(r2, p)))))
    else:
        for p1 in range(4):
            for p2 in range(4):
                if p1 != p2:
                    out.append(tuple(sorted((C.carta(r1, p1), C.carta(r2, p2)))))
    return out


def clase_de_combo(a, b):
    """Etiqueta de la clase de un combo: (A♠, K♠) -> 'AKs'."""
    ra, rb = C.rango_de(a), C.rango_de(b)
    if ra == rb:
        return etiqueta(ra, rb, "p")
    if ra < rb:
        ra, rb, a, b = rb, ra, b, a
    return etiqueta(ra, rb, "s" if C.palo_de(a) == C.palo_de(b) else "o")


# --- Ranking por equity contra mano al azar ----------------------------------------------

_RANK = None


def cargar_rank169():
    """{'orden': [clases de mejor a peor], 'equity': {...}} desde datos/rank169.json."""
    global _RANK
    if _RANK is None:
        with open(RUTA_RANK169, encoding="utf-8") as f:
            _RANK = json.load(f)
    return _RANK


def clases_top(pct):
    """Clases del top `pct` % de combos (de 1326), mejores primero.

    La clase entra si su punto medio acumulado cae dentro del objetivo: con un
    pct que coincide con un borde de clase (p. ej. 14,3 % = 190 combos) entra
    exactamente hasta esa clase; en otro caso, se redondea a la clase más cercana.
    """
    orden = cargar_rank169()["orden"]
    objetivo = pct / 100.0 * 1326
    acumulado = 0
    out = []
    for clase in orden:
        n = n_combos(clase)
        if acumulado + n / 2.0 <= objetivo + 1e-9:
            out.append(clase)
        acumulado += n
    return out


def pct_acumulado(clase):
    """% de combos acumulado hasta esa clase inclusive (su 'rank' en §1.5)."""
    acumulado = 0
    for c in cargar_rank169()["orden"]:
        acumulado += n_combos(c)
        if c == clase:
            return acumulado / 1326 * 100
    raise KeyError(clase)


# --- Rangos con pesos ---------------------------------------------------------------------

class Rango:
    """Combos vivos con su peso, listos para sortear (proporcional a w(h), §1.3)."""

    __slots__ = ("combos", "masks", "pesos", "acum", "total")

    def __init__(self, combos_pesos, muertas=0):
        """combos_pesos: dict o lista de ((a, b), w). `muertas`: máscara de cartas
        que no pueden estar en ningún combo."""
        items = combos_pesos.items() if isinstance(combos_pesos, dict) else combos_pesos
        self.combos, self.masks, self.pesos = [], [], []
        for (a, b), w in items:
            m = (1 << a) | (1 << b)
            if w > 0 and not (m & muertas):
                self.combos.append((a, b))
                self.masks.append(m)
                self.pesos.append(float(w))
        self._acumular()

    def _acumular(self):
        acum, s = [], 0.0
        for w in self.pesos:
            s += w
            acum.append(s)
        self.acum, self.total = acum, s

    def __len__(self):
        return len(self.combos)

    def vacio(self):
        return not self.combos

    def sortear_indice(self, u):
        """u en [0,1) -> índice del combo, con probabilidad w/Σw."""
        i = bisect.bisect_right(self.acum, u * self.total)
        return i if i < len(self.acum) else len(self.acum) - 1

    def filtrar(self, muertas):
        """Copia sin los combos que usan una carta de `muertas`."""
        return Rango(list(zip(self.combos, self.pesos)), muertas)

    def reajustar(self, verosimilitud, piso=0.02):
        """Bayes con pesos (§2.1): w' = max(w·P(a|h), piso·w), luego se normaliza.
        `verosimilitud(a, b)` devuelve P(a|h) del combo. Devuelve un rango nuevo."""
        nuevos = []
        for (a, b), w in zip(self.combos, self.pesos):
            nuevos.append(((a, b), max(w * verosimilitud(a, b), piso * w)))
        r = Rango(nuevos)
        if r.total > 0:
            r.pesos = [w / r.total for w in r.pesos]
            r._acumular()
        return r

    def conteo_por_clase(self):
        """{'AKs': 3, ...}: cuántos combos vivos hay de cada clase."""
        out = {}
        for a, b in self.combos:
            k = clase_de_combo(a, b)
            out[k] = out.get(k, 0) + 1
        return out

    def peso_total_por_clase(self):
        out = {}
        for (a, b), w in zip(self.combos, self.pesos):
            k = clase_de_combo(a, b)
            out[k] = out.get(k, 0.0) + w
        return out


def rango_de_clases(clases, muertas=0, peso=1.0):
    """Rango con todos los combos de las clases dadas (iterable de etiquetas o
    dict clase -> peso), sin los que usan cartas muertas."""
    pesos = clases if isinstance(clases, dict) else {c: peso for c in clases}
    items = []
    for clase, w in pesos.items():
        for combo in combos_de_clase(clase):
            items.append((combo, w))
    return Rango(items, muertas)


def rango_alazar(muertas=0):
    """Mano al azar: los 1326 combos con peso 1."""
    return rango_de_clases(CLASES_169, muertas)


def rango_top(pct, muertas=0):
    """Top `pct` % de manos (§1.5), sin cartas muertas."""
    return rango_de_clases(clases_top(pct), muertas)


# --- Notación de rangos: "QQ+, AK" ---------------------------------------------------------

_TOKEN = re.compile(r"^([2-9TJQKA])([2-9TJQKA])([so]?)(\+?)$")
_TOKEN_GUION = re.compile(r"^([2-9TJQKA])([2-9TJQKA])([so]?)-([2-9TJQKA])([2-9TJQKA])([so]?)$")


def clases_de_texto(texto):
    """'QQ+, AK' -> ['QQ','KK','AA','AKs','AKo']. Soporta XX, XX+, XYs, XYo, XY
    (ambas), XY+ (sube la segunda carta hasta debajo de la primera) y rangos
    con guion ('77-99', 'A2s-A5s')."""
    out = []
    for token in re.split(r"[,\s]+", texto.strip()):
        if not token:
            continue
        g = _TOKEN_GUION.match(token)
        if g:
            r1, r2, t1, s1, s2, t2 = g.groups()
            a1, a2, b1, b2 = (SIMB.index(x) + 2 for x in (r1, r2, s1, s2))
            if a1 == a2 and b1 == b2:
                for r in range(min(a1, b1), max(a1, b1) + 1):
                    out.append(etiqueta(r, r, "p"))
            elif a1 == b1:
                for r in range(min(a2, b2), max(a2, b2) + 1):
                    for t in (t1 or "so"):
                        out.append(etiqueta(a1, r, t))
            else:
                raise ValueError(f"rango con guion no soportado: {token}")
            continue
        m = _TOKEN.match(token)
        if not m:
            raise ValueError(f"token de rango inválido: {token!r}")
        r1, r2 = (SIMB.index(x) + 2 for x in m.group(1, 2))
        tipo, mas = m.group(3), m.group(4) == "+"
        if r1 < r2:
            r1, r2 = r2, r1
        if r1 == r2:
            for r in (range(r1, 15) if mas else [r1]):
                out.append(etiqueta(r, r, "p"))
        else:
            for r in (range(r2, r1) if mas else [r2]):
                for t in (tipo or "so"):
                    out.append(etiqueta(r1, r, t))
    vistos, unicos = set(), []
    for c in out:
        if c not in vistos:
            vistos.add(c)
            unicos.append(c)
    return unicos


def rango_de_texto(texto, muertas=0):
    return rango_de_clases(clases_de_texto(texto), muertas)


# --- Categoría de una mano en un board (§2.2) -------------------------------------------------

FUERTE, MEDIA, PROYECTO, AIRE = "fuerte", "media", "proyecto", "aire"
MIN_OUTS_PROYECTO = 8


def _clase_board(board):
    """Clase de mano que forma el board solo (3, 4 o 5 cartas)."""
    if len(board) == 5:
        return C.clase_de_rank(C.evaluar(board))
    cuentas = {}
    for c in board:
        cuentas[C.rango_de(c)] = cuentas.get(C.rango_de(c), 0) + 1
    v = sorted(cuentas.values(), reverse=True)
    if v[0] == 4:
        return C.POKER
    if v[0] == 3:
        return C.TRIO
    if v[0] == 2 and len(v) > 1 and v[1] == 2:
        return C.DOBLE_PAR
    if v[0] == 2:
        return C.PAR
    return C.CARTA_ALTA


def outs_de_proyecto(mano, board):
    """Cartas que le dan a `mano` escalera o color que el board solo no da."""
    if len(board) not in (3, 4):
        return 0
    usadas = set(mano) | set(board)
    outs = 0
    for c in C.TODAS:
        if c in usadas:
            continue
        rank_total = C.evaluar(list(mano) + list(board) + [c])
        clase_total = C.clase_de_rank(rank_total)
        if clase_total > C.ESCALERA:
            continue
        # Solo cuenta si el board con esa carta no forma ya esa clase por sí solo.
        if len(board) == 3:
            solo_board = C.CARTA_ALTA          # 4 cartas solas no pueden formar escalera ni color
        else:
            solo_board = C.clase_de_rank(C.evaluar(list(board) + [c]))
        if clase_total < solo_board:
            outs += 1
    return outs


def categoria_mano(mano, board):
    """Categoría de `mano` (2 ids) en `board` (3 a 5 ids) para las plantillas de §2.2:

      fuerte    top pair o mejor: overpair, dos pares con las dos cartas, trío,
                escalera, color...
      media     pareja menor: pareja de bolsillo bajo la carta alta del board,
                segunda o tercera pareja.
      proyecto  sin pareja pero con 8 o más outs (color o escalera abierta).
      aire      todo lo demás (un gutshot cuenta como aire).
    """
    board = list(board)
    if len(board) < 3:
        raise ValueError("la categoría necesita al menos el flop")
    h1, h2 = mano
    rangos_board = [C.rango_de(c) for c in board]
    maximo = max(rangos_board)
    todas = [h1, h2] + board
    rank_total = C.evaluar(todas)
    clase_total = C.clase_de_rank(rank_total)
    clase_board = _clase_board(board)

    # 1) Trío o mejor que las cartas de Bender (el rival) hacen realidad.
    if clase_total <= C.TRIO:
        mejora_clase = clase_total < clase_board
        mejora_jugada = (len(board) == 5 and clase_total in (C.ESCALERA, C.COLOR, C.ESCALERA_DE_COLOR)
                         and rank_total < C.evaluar(board))
        if mejora_clase or mejora_jugada:
            return FUERTE

    # 2) Parejas formadas con las cartas privadas.
    r1, r2 = C.rango_de(h1), C.rango_de(h2)
    if r1 == r2:
        return FUERTE if r1 > maximo else MEDIA          # overpair vs. pareja de bolsillo menor
    pares = [r for r in (r1, r2) if r in rangos_board]
    if len(pares) == 2:
        return FUERTE                                     # dos pares con las dos cartas
    if len(pares) == 1:
        return FUERTE if pares[0] == maximo else MEDIA    # top pair vs. segunda o tercera pareja

    # 3) Sin pareja: ¿proyecto con 8 o más outs?
    if outs_de_proyecto(mano, board) >= MIN_OUTS_PROYECTO:
        return PROYECTO
    return AIRE


# --- Generación del ranking de 169 clases -------------------------------------------------------

def _equity_clase(args):
    """Equity (con empates como 1/2) de una clase contra una mano al azar, por Monte Carlo."""
    clase, n, semilla = args
    import random
    rng = random.Random(semilla)
    h1, h2 = combos_de_clase(clase)[0]
    ev7 = C.evaluar7
    base = [c for c in range(52) if c != h1 and c != h2]
    acum = 0.0
    for _ in range(n):
        cinco_y_dos = rng.sample(base, 7)            # 5 del board + 2 del rival
        board = cinco_y_dos[:5]
        mio = ev7(h1, h2, *board)
        rival = ev7(cinco_y_dos[5], cinco_y_dos[6], *board)
        if mio < rival:
            acum += 1.0
        elif mio == rival:
            acum += 0.5
    return clase, acum / n


def generar_rank169(n_por_clase=400_000, procesos=None, ruta=RUTA_RANK169):
    """Calcula la equity de las 169 clases contra una mano al azar y guarda el
    ranking en datos/rank169.json (de mejor a peor)."""
    from multiprocessing import Pool
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    trabajos = [(c, n_por_clase, 1000 + i) for i, c in enumerate(CLASES_169)]
    with Pool(procesos) as pool:
        resultados = dict(pool.imap_unordered(_equity_clase, trabajos))
    orden = sorted(CLASES_169, key=lambda c: -resultados[c])
    datos = {"n_por_clase": n_por_clase, "orden": orden,
             "equity": {c: round(resultados[c], 5) for c in orden}}
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    global _RANK
    _RANK = None
    return datos


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 400_000
    d = generar_rank169(n)
    print(f"rank169 generado con {n} simulaciones por clase en {RUTA_RANK169}")
    print("primeras:", d["orden"][:10])
