"""Capa 0 · Interpretación de los mensajes de la mesa.

Convierte el JSON del protocolo (docs/protocolo.md) en objetos cómodos y trae
las cuentas de apuestas, que son un port de `Turno.Apostar` / `ApostarPozo` del
SDK de Go (pkg/botsdk/botsdk.go): ahí está la aritmética que la mesa acepta, y
el tamaño x (§1.8) y z (§2.7) del .tex usan exactamente esa misma cuenta.

Notación del .tex (§0): P pozo, C lo que cuesta igualar, x = (monto - apuesta
actual) / (P + C).
"""

import time
from dataclasses import dataclass, field

ETAPAS = ("preflop", "flop", "turn", "river")
PALOS = "cdhs"                     # 0=tréboles 1=diamantes 2=corazones 3=picas
RANGOS = {11: "J", 12: "Q", 13: "K", 14: "A", 10: "T"}
APUESTAS = ("bet", "raise", "allin")


# --- Cartas -----------------------------------------------------------------------

def carta_de_dict(d):
    """{"rango":14,"palo":3} -> (14, 3). Las cartas se manejan como tuplas."""
    return (int(d["rango"]), int(d["palo"]))


def texto_carta(c):
    rango, palo = c
    return f"{RANGOS.get(rango, str(rango))}{PALOS[palo]}"


def texto_cartas(cartas):
    return " ".join(texto_carta(c) for c in cartas) if cartas else "-"


# --- Estado público -----------------------------------------------------------------

@dataclass
class Jugador:
    id: str
    nombre: str = ""
    saldo: int = 0
    apuesta_ronda: int = 0
    activo: bool = False        # sigue EN LA MANO (no hizo fold)
    en_torneo: bool = False     # sigue en la partida (le quedan fichas)
    allin: bool = False
    en_mano: bool = False       # recibió cartas en la mano en curso
    silla: int = 0

    @staticmethod
    def de_dict(d):
        return Jugador(
            id=d.get("id", ""), nombre=d.get("nombre", ""), saldo=int(d.get("saldo", 0)),
            apuesta_ronda=int(d.get("apuesta_ronda", 0)), activo=bool(d.get("activo", False)),
            en_torneo=bool(d.get("en_torneo", False)), allin=bool(d.get("allin", False)),
            en_mano=bool(d.get("en_mano", False)), silla=int(d.get("posicion_silla", 0)),
        )


@dataclass
class EstadoPublico:
    id_mano: str = ""
    etapa: str = "preflop"
    comunitarias: list = field(default_factory=list)
    pozo: int = 0
    apuesta_actual: int = 0
    subida_minima: int = 0
    ciega_chica: int = 50
    ciega_grande: int = 100
    boton: int = 0
    jugadores: list = field(default_factory=list)
    historial: list = field(default_factory=list)     # lista de dicts del protocolo

    @staticmethod
    def de_dict(d):
        d = d or {}
        return EstadoPublico(
            id_mano=d.get("id_mano", ""), etapa=d.get("etapa", "preflop"),
            comunitarias=[carta_de_dict(c) for c in d.get("comunitarias") or []],
            pozo=int(d.get("pozo", 0)), apuesta_actual=int(d.get("apuesta_actual", 0)),
            subida_minima=int(d.get("subida_minima", 0)),
            # Se leen del estado en vez de suponerlas (docs/protocolo.md).
            ciega_chica=int(d.get("ciega_chica") or 50), ciega_grande=int(d.get("ciega_grande") or 100),
            boton=int(d.get("posicion_boton", 0)),
            jugadores=[Jugador.de_dict(j) for j in d.get("jugadores") or []],
            historial=list(d.get("historial_acciones") or []),
        )


# --- Posiciones ---------------------------------------------------------------------

def posiciones(estado):
    """Devuelve {id_jugador: nombre de posición} de los jugadores de la mano.

    Las ciegas no aparecen en el historial, así que la posición se deduce del
    botón y las sillas (en sentido horario). Con 6 jugadores: SB, BB, UTG, HJ,
    CO, BTN; con 5 no hay UTG; con 4 tampoco HJ; con 3, SB/BB/BTN. En heads-up
    el botón es la ciega chica y se nombra "BTN/SB"; el otro es "BB".
    """
    en_mano = [j for j in estado.jugadores if j.en_mano]
    if not en_mano:
        return {}
    # Distancia horaria desde el botón: el botón queda de último. Cualquier
    # módulo >= (silla máxima + 1) da el mismo orden relativo.
    orden = sorted(en_mano, key=lambda j: (j.silla - estado.boton - 1) % 64)
    n = len(orden)
    if n == 1:
        return {orden[0].id: "BTN/SB"}
    if n == 2:
        # orden = [no botón, botón]
        return {orden[0].id: "BB", orden[1].id: "BTN/SB"}
    nombres = {3: ["SB", "BB", "BTN"], 4: ["SB", "BB", "CO", "BTN"], 5: ["SB", "BB", "HJ", "CO", "BTN"],
               6: ["SB", "BB", "UTG", "HJ", "CO", "BTN"]}.get(n)
    if nombres is None:
        # Mesas de 7-8 (no se juegan en el torneo): el resto va como "UTG".
        nombres = ["SB", "BB"] + ["UTG"] * (n - 5) + ["HJ", "CO", "BTN"]
    return {j.id: nombres[i] for i, j in enumerate(orden)}


# --- Acción segura --------------------------------------------------------------------

def accion_segura(validas):
    """Lo que la mesa jugaría por nosotros: check si es gratis, si no fold."""
    return {"tipo": "check"} if "check" in (validas or []) else {"tipo": "fold"}


def accion_es_valida(accion, validas):
    """Última red de seguridad antes de enviar: el tipo está permitido y los
    montos son enteros. Una acción inválida cuesta lo mismo que un timeout."""
    if not isinstance(accion, dict) or accion.get("tipo") not in (validas or []):
        return False
    if accion["tipo"] in ("bet", "raise"):
        return isinstance(accion.get("monto"), int) and not isinstance(accion.get("monto"), bool) and accion["monto"] > 0
    return True


# --- Turno ------------------------------------------------------------------------------

class Turno:
    """Todo lo que Bender sabe en el momento de decidir, ya masticado."""

    def __init__(self, estado, mi_id, mano, validas, timeout_ms=0, stacks0=None):
        self.estado = estado
        self.mi_id = mi_id
        # S⁰ (§1.4): fichas de cada jugador AL EMPEZAR LA MANO {id: saldo + lo que ya puso}. Si no se conocen (reconexión a
        # mitad de mano, pruebas sueltas) se estiman con el estado actual: saldo + apuesta_ronda.
        self.stacks0 = dict(stacks0) if stacks0 else None
        self.mano = list(mano or [])
        self.validas = list(validas or [])
        self.timeout_ms = timeout_ms
        # Nos buscamos por id_jugador (el de la bienvenida), nunca por el token.
        self.yo = next((j for j in estado.jugadores if j.id == mi_id), Jugador(id=mi_id))

    # --- Lo que se ve en la mesa ---
    @property
    def etapa(self):
        return self.estado.etapa

    @property
    def comunitarias(self):
        return self.estado.comunitarias

    @property
    def bb(self):
        return self.estado.ciega_grande or 100

    @property
    def rivales(self):
        """Rivales que siguen en la mano (no se retiraron)."""
        return [j for j in self.estado.jugadores if j.id != self.mi_id and j.activo and j.en_mano]

    @property
    def mi_posicion(self):
        return posiciones(self.estado).get(self.mi_id, "")

    # --- Cuentas de §0 ---
    @property
    def P(self):
        """Pozo ahora, con las apuestas de esta ronda (§0)."""
        return self.estado.pozo

    @property
    def C(self):
        """Fichas que hay que agregar para igualar. 0 si se puede pasar gratis."""
        return max(0, self.estado.apuesta_actual - self.yo.apuesta_ronda)

    @property
    def pozo_si_pagas(self):
        return self.estado.pozo + self.C

    @property
    def techo(self):
        """Total máximo al que se puede llevar la apuesta: el all-in."""
        return self.yo.saldo + self.yo.apuesta_ronda

    @property
    def subida_minima_total(self):
        """Total mínimo que la mesa acepta como bet o raise."""
        return self.estado.apuesta_actual + self.estado.subida_minima

    def stack_efectivo_bb(self):
        """S_ef (§1.4): min(S⁰_Bender, max_i S⁰_i) / bb, con S⁰ = fichas AL EMPEZAR LA MANO (saldo + lo ya puesto).

        Con S⁰ el modo es el mismo durante toda la mano. (Con las fichas que QUEDAN detrás, un rival all-in valía 0 bb y
        Bender entraba en push/fold ante cualquier all-in: llegó a retirar AA contra un all-in de 100 bb.)"""
        yo0 = self._s0(self.yo)
        if self.stacks0:
            rivales0 = [v for k, v in self.stacks0.items() if k != self.mi_id]       # a quienes se repartieron cartas
        else:
            rivales0 = [self._s0(j) for j in self.rivales]
        if not rivales0:
            return yo0 / self.bb
        return min(yo0, max(rivales0)) / self.bb

    def _s0(self, jugador):
        if self.stacks0 and jugador.id in self.stacks0:
            return self.stacks0[jugador.id]
        return jugador.saldo + jugador.apuesta_ronda

    def fraccion_de_monto(self, monto):
        """x (§1.8) o z (§2.7): (monto - apuesta actual) / (P + C)."""
        base = self.pozo_si_pagas
        return (monto - self.estado.apuesta_actual) / base if base > 0 else 0.0

    # --- Acciones (siempre válidas) ---
    def puede(self, tipo):
        return tipo in self.validas

    def pagar(self):
        """Iguala; si no hay nada que igualar, pasa."""
        if self.puede("call"):
            return {"tipo": "call"}
        if self.puede("check"):
            return {"tipo": "check"}
        if self.puede("allin"):
            return {"tipo": "allin"}
        return {"tipo": "fold"}

    def pasar_o_retirarse(self):
        return accion_segura(self.validas)

    def todo(self):
        return {"tipo": "allin"} if self.puede("allin") else self.pagar()

    def apostar(self, total):
        """Lleva la apuesta de la ronda hasta `total` (el TOTAL, no el
        incremento). Port de Turno.Apostar del SDK de Go: elige bet o raise,
        recorta a la subida mínima y al techo, y convierte a all-in lo que
        llegue al techo. Si no se puede subir, cae a la mejor acción pasiva."""
        total = int(total)
        tipo = "bet" if self.estado.apuesta_actual <= self.yo.apuesta_ronda else "raise"
        techo = self.techo
        if not self.puede(tipo):
            if self.puede("allin") and total >= techo:
                return {"tipo": "allin"}
            if self.puede("check"):
                return {"tipo": "check"}
            if self.puede("call"):
                return {"tipo": "call"}
            return {"tipo": "fold"}
        if total >= techo:
            # Llegar al techo es un all-in: se declara así para que la mesa
            # aplique la regla de all-in corto en vez de rechazarlo.
            if self.puede("allin"):
                return {"tipo": "allin"}
            total = techo
        minimo = self.subida_minima_total
        if total < minimo:
            total = minimo
        if total > techo:
            # La subida mínima no entra en el stack: solo queda el all-in.
            if self.puede("allin"):
                return {"tipo": "allin"}
            if self.puede("call"):
                return {"tipo": "call"}
            return {"tipo": "fold"}
        return {"tipo": tipo, "monto": total}

    def apostar_pozo(self, fraccion):
        """Port de ApostarPozo: apuesta actual + fracción de (P + C)."""
        return self.apostar(self.estado.apuesta_actual + int(self.pozo_si_pagas * fraccion))


# --- Seguimiento de la mesa y de la mano ------------------------------------------------

class SeguimientoMesa:
    """Recuerda en qué mesa y mano estamos. Lo necesita el reloj adaptativo
    (§1.2): manos jugadas en la mesa y segundos desde su primera mano."""

    def __init__(self):
        self.ids_mesa = frozenset()
        self.manos_mesa = 0
        self.inicio_mesa = time.monotonic()
        self.id_mano = ""
        self.mano = []            # nuestras cartas de la mano en curso
        self.id_mano_cartas = ""  # de qué mano son (tras reconectar a mitad de mano no hay)
        self.ultimo_estado = None
        self.stacks0 = {}         # S⁰ de la mano en curso: {id: saldo + apuesta_ronda en mano_inicio} (§1.4)
        self.id_mano_stacks = ""

    def nueva_mano(self, estado, cartas):
        ids = frozenset(j.id for j in estado.jugadores)
        if ids != self.ids_mesa:
            # Cambió el conjunto de sentados: es una mesa nueva (el torneo
            # re-sortea las mesas en cada ronda).
            self.ids_mesa = ids
            self.manos_mesa = 0
            self.inicio_mesa = time.monotonic()
        self.id_mano = estado.id_mano
        self.mano = list(cartas)
        self.id_mano_cartas = estado.id_mano
        self.ultimo_estado = estado
        # Fichas al empezar la mano de cada jugador al que se le repartieron cartas (con las ciegas ya puestas o no: la suma es la misma).
        self.stacks0 = {j.id: j.saldo + j.apuesta_ronda for j in estado.jugadores if j.en_mano}
        self.id_mano_stacks = estado.id_mano

    def stacks0_de(self, estado):
        """S⁰ de esta mano, o None si no se vio el inicio de la mano (reconexión a mitad de mano)."""
        return self.stacks0 if self.stacks0 and self.id_mano_stacks == estado.id_mano else None

    def mano_terminada(self):
        self.manos_mesa += 1

    def tengo_cartas(self, estado):
        return len(self.mano) == 2 and self.id_mano_cartas == estado.id_mano

    @property
    def segundos_mesa(self):
        return time.monotonic() - self.inicio_mesa
