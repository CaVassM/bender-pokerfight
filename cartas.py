"""Capa 1 · Cartas y evaluador de manos.

Las cartas se manejan como enteros 0..51: id = (rango - 2) * 4 + palo, con
rango 2..14 (J=11, Q=12, K=13, A=14) y palo 0=tréboles, 1=diamantes,
2=corazones, 3=picas (el mismo orden del protocolo). Ese es también el
codificado que usa `phevaluator`, así que no hay conversión al evaluar.

Evaluador: `phevaluator` (extensión en C). Se mide primero: llamando directo a
`_pheval.evaluate_7cards` salen unas 7,5 M evaluaciones/s en esta máquina; el
envoltorio público `evaluate_cards` ~1,3 M/s (la meta era >= 300 000/s). Si el
módulo C privado no se pudiera importar, se cae al envoltorio público.

En phevaluator un número MENOR es una mano MÁS fuerte (1 = escalera real,
7462 = la peor carta alta). Un empate exacto devuelve el mismo número.
"""

try:
    from phevaluator import _pheval as _c
    evaluar5, evaluar6, evaluar7 = _c.evaluate_5cards, _c.evaluate_6cards, _c.evaluate_7cards
except ImportError:                                  # pragma: no cover (respaldo)
    from phevaluator import evaluate_cards as _ev

    def evaluar5(a, b, c, d, e): return _ev(a, b, c, d, e)
    def evaluar6(a, b, c, d, e, f): return _ev(a, b, c, d, e, f)
    def evaluar7(a, b, c, d, e, f, g): return _ev(a, b, c, d, e, f, g)

PALOS = "cdhs"
SIMBOLOS_RANGO = "23456789TJQKA"
TODAS = tuple(range(52))

# Clases de mano según el número de phevaluator (cotas inferiores incluidas).
CLASES = ("escalera de color", "poker", "full house", "color", "escalera", "trio", "doble par", "par", "carta alta")
_LIMITES = (1, 11, 167, 323, 1600, 1610, 2468, 3326, 6186)   # inicio de cada clase
ESCALERA_DE_COLOR, POKER, FULL, COLOR, ESCALERA, TRIO, DOBLE_PAR, PAR, CARTA_ALTA = range(9)


def clase_de_rank(rank):
    """Índice de la clase de mano (0 = escalera de color ... 8 = carta alta)."""
    for i in range(8, -1, -1):
        if rank >= _LIMITES[i]:
            return i
    return 0


# --- Conversiones ---------------------------------------------------------------------

def carta(rango, palo):
    return (rango - 2) * 4 + palo


def rango_de(c):
    return c // 4 + 2


def palo_de(c):
    return c % 4


def de_tupla(t):
    """(rango, palo) del protocolo -> id."""
    return carta(t[0], t[1])


def a_tupla(c):
    return (rango_de(c), palo_de(c))


def de_texto(s):
    """'As' -> 51."""
    return carta(SIMBOLOS_RANGO.index(s[0].upper()) + 2, PALOS.index(s[1].lower()))


def cartas_de_texto(s):
    """'As Jh' o 'AsJh' -> [51, ...]."""
    s = s.replace(" ", "").replace(",", "")
    return [de_texto(s[i:i + 2]) for i in range(0, len(s), 2)]


def texto(c):
    return f"{SIMBOLOS_RANGO[rango_de(c) - 2]}{PALOS[palo_de(c)]}"


def texto_cartas(cs):
    return " ".join(texto(c) for c in cs) if cs else "-"


def mascara(cartas):
    """Entero con un bit por carta: sirve para saber en O(1) si dos manos comparten carta."""
    m = 0
    for c in cartas:
        m |= 1 << c
    return m


# --- Evaluación -----------------------------------------------------------------------

def evaluar(cartas):
    """Rank de la mejor mano de 5 entre 5, 6 o 7 cartas (menor = más fuerte)."""
    n = len(cartas)
    if n == 7:
        return evaluar7(*cartas)
    if n == 6:
        return evaluar6(*cartas)
    if n == 5:
        return evaluar5(*cartas)
    raise ValueError(f"se necesitan entre 5 y 7 cartas, llegaron {n}")
