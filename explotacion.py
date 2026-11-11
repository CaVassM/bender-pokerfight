"""Explotación · de la lectura a la decisión (bender/docs/bender_formulas.tex, §3).

Principio (§3): explotar no es agregar reglas nuevas, es meter los números DEL RIVAL (su c_i y su rango) en las
mismas fórmulas de la Capa 1. Lo único nuevo es CUÁNTO confiar en esos números:

  §3.2  ρ_i = ρ_max · max(0, 1 − κ·σ_i / |p̂_i − m|)     (0 si n_i < n_min o p̂_i = m)
  §3.3  θ_i = (1 − ρ_i)·θ_base + ρ_i·θ̂_i                 (c_i por tamaño de apuesta y ancho del rango preflop)
  §3.4  ajustes por tipo cuando π_t ≥ τ, y contraestrategia del bot del kit reconocido (huella ≥ 0,9)

`Lectura` resume lo que Bender cree de UN rival en esta decisión; capa1.py y poblacion.py la consumen.
"""

TIPOS_SIN_FAROL = ("station", "maniaco", "aleatorio")


def rho_de(beta, m, cfg):
    """§3.2. `beta` es la estadística del rival (rivales.Beta); `m`, el valor de la población."""
    distancia = abs(beta.p - m)
    if beta.n < cfg["n_min"] or distancia < 1e-12:
        return 0.0
    return cfg["rho_max"] * max(0.0, 1.0 - cfg["kappa"] * beta.sigma / distancia)


def theta(base, medido, rho):
    """§3.3: θ = (1 − ρ)·θ_base + ρ·θ̂."""
    return (1.0 - rho) * base + rho * medido


class Lectura:
    """Lo que Bender cree de un rival en esta decisión."""

    __slots__ = ("id", "pi", "tipo", "bot", "bot_p", "stats", "manos")

    def __init__(self, id_):
        self.id = id_
        self.pi, self.tipo = {}, None          # creencia sobre su tipo y el tipo dominante (π_t >= τ) si lo hay
        self.bot, self.bot_p = None, 0.0       # bot del kit reconocido por la huella (>= 0,9) y su probabilidad
        self.stats = {}                        # nombre -> {p, sigma, n, rho}
        self.manos = 0

    def a_info(self):
        return {"tipo": self.tipo, "pi": {t: round(v, 2) for t, v in self.pi.items()}, "bot": self.bot,
                "manos": self.manos, "stats": {n: {k: round(v, 3) for k, v in s.items()} for n, s in self.stats.items()}}


def lectura_de(riv, params, usar_stats=True, usar_bots=True):
    """Lectura de un rival (rivales.Rival) con las reglas de §3.2-§3.4."""
    cfg = params["explotacion"]
    m = params["beta"]["m"]
    lec = Lectura(riv.id)
    lec.pi = riv.pi()
    lec.manos = riv.contadores["manos"]
    mejor = max(lec.pi, key=lec.pi.get)
    lec.tipo = mejor if lec.pi[mejor] >= cfg["tau"] else None
    for nombre, beta in riv.stats.items():
        rho = rho_de(beta, m[nombre], cfg) if usar_stats else 0.0
        lec.stats[nombre] = {"p": beta.p, "sigma": beta.sigma, "n": beta.n, "rho": rho}
    if usar_bots:
        r = riv.bot_reconocido()
        if r is not None:
            lec.bot, lec.bot_p = r
    return lec


def c_mezclada(c_base, lec, x, params):
    """§3.3: el c_i que entra a la fórmula, mezclando el del modelo (rango + plantillas) con el medido del rival
    ("sigue ante apuesta chica" si x <= 0,6, "grande" si no)."""
    nombre = "sigue_chica" if x <= params["beta"]["x_chica_max"] else "sigue_grande"
    s = lec.stats.get(nombre)
    if s is None or s["rho"] <= 0.0:
        return c_base
    return min(0.98, max(0.02, theta(c_base, s["p"], s["rho"])))


def datos_para_rangos(lec):
    """Lo que poblacion.rango_preflop necesita de la lectura: p̂ y ρ de VPIP y PFR, y el bot reconocido."""
    if lec is None:
        return None
    return {"vpip": (lec.stats["vpip"]["p"], lec.stats["vpip"]["rho"]), "pfr": (lec.stats["pfr"]["p"], lec.stats["pfr"]["rho"]),
            "bot": lec.bot, "tipo": lec.tipo}


def sin_farol(lecturas):
    """§3.4: si TODOS los rivales en la mano son station, maníaco o aleatorio (con π_t >= τ), no se farolea.
    Devuelve el motivo (texto) o None."""
    if lecturas and all(l.tipo in TIPOS_SIN_FAROL for l in lecturas):
        return "tipo: no se farolea a " + ", ".join(sorted({l.tipo for l in lecturas}))
    return None
