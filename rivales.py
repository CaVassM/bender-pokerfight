"""Capa 2 · Lectura de rivales: memoria por ID (bender/docs/bender_formulas.tex, §2).

Qué guarda de cada rival (por su `id_jugador`, estable durante todo el campeonato):
  - estadísticas con prior Beta (§2.5): VPIP, PFR, "sigue ante apuesta chica" (x <= 0,6) y
    "sigue ante apuesta grande" (x > 0,6). Cada una es un par (α, β) con olvido λ (§2.6);
  - la creencia sobre su TIPO (nit, TAG, station, maníaco, aleatorio) en logaritmos (§2.3);
  - el posterior de la HUELLA de sus montos (§2.7): ¿es un bot copiado del kit?;
  - contadores crudos (manos, cajas de z, acciones) para calibrar y depurar.

Aprende de TODAS las manos, también las que Bender no juega (recibe cada `estado`), y de las
cartas mostradas en el showdown (`mano_fin.mostradas`). Se guarda en disco al terminar cada mano.

`Observador` convierte los mensajes de la mesa en eventos por acción, reconstruyendo el pozo y la
apuesta de cada momento (las ciegas no aparecen en el historial), y de ahí sale z (§2.7):
    z = (monto − apuesta actual) / (pozo + lo que le falta para igualar a quien apuesta).
"""

import json
import math
import os

import cartas as C
import poblacion as POB
import rangos as R
from estado import APUESTAS, EstadoPublico

DIR_DEFECTO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos", "rivales")
CARTAS_DE_CALLE = {"flop": 3, "turn": 4, "river": 5}
TIPOS_PREFLOP = ("F", "C", "R")


# --- Utilidades ------------------------------------------------------------------------------

def caja_de_z(z, cfg):
    """Índice de la caja de z (§2.7): la más cercana a ±tolerancia; si ninguna, la última ("otro")."""
    cajas, tol = cfg["cajas"], cfg["tolerancia"]
    mejor = min(range(len(cajas)), key=lambda i: abs(z - cajas[i]))
    return mejor if abs(z - cajas[mejor]) <= tol + 1e-9 else len(cajas)


def posterior_huella(cajas_vistas, cfg):
    """P(bot | z_1..z_n) ∝ P(bot)·Π P(z_i|bot) (§2.7). `cajas_vistas`: lista de índices de caja.
    Devuelve {bot: probabilidad}."""
    tabla, prior = cfg["tabla"], cfg["prior"]
    logs = {}
    for bot, fila in tabla.items():
        lp = math.log(max(prior.get(bot, 0.0), 1e-12))
        for i in cajas_vistas:
            lp += math.log(max(fila[i], 1e-6))
        logs[bot] = lp
    return _normalizar(logs)


def _normalizar(logs, piso=0.0):
    """log -> probabilidades restando el máximo (evita underflow), con piso opcional."""
    m = max(logs.values())
    exps = {k: math.exp(v - m) for k, v in logs.items()}
    s = sum(exps.values())
    p = {k: v / s for k, v in exps.items()}
    if piso > 0:
        p = {k: max(v, piso) for k, v in p.items()}
        s = sum(p.values())
        p = {k: v / s for k, v in p.items()}
    return p


class Beta:
    """Frecuencia con prior Beta y olvido (§2.5, §2.6). α0 = s·m, β0 = s·(1−m)."""

    def __init__(self, m, s, alfa=None, beta=None, k=0, n=0):
        self.alfa = s * m if alfa is None else alfa
        self.beta = s * (1.0 - m) if beta is None else beta
        self.k, self.n = k, n            # conteos crudos (sin olvido), para calibrar y para n_min de §3.2

    def observar(self, si, lam):
        """Primero se olvida (α, β ← λα, λβ), luego se suma la observación."""
        self.alfa *= lam
        self.beta *= lam
        if si:
            self.alfa += 1.0
            self.k += 1
        else:
            self.beta += 1.0
        self.n += 1

    @property
    def p(self):
        return self.alfa / (self.alfa + self.beta)

    @property
    def sigma(self):
        t = self.alfa + self.beta
        return math.sqrt(self.p * (1.0 - self.p) / (t + 1.0))

    def a_dict(self):
        return {"alfa": self.alfa, "beta": self.beta, "k": self.k, "n": self.n}


class Rival:
    """Todo lo que Bender sabe de un rival."""

    ESTADISTICAS = ("vpip", "pfr", "sigue_chica", "sigue_grande")

    def __init__(self, id_, params, datos=None):
        self.id = id_
        self.p = params
        b = params["beta"]
        self.stats = {n: Beta(b["m"][n], b["s"][n]) for n in self.ESTADISTICAS}
        self.log_pi = {t: math.log(params["prior_tipos"][t]) for t in params["tipos"]}
        h = params["huella"]
        pr = h["prior"]
        z = sum(pr.get(bot, 0.0) for bot in h["tabla"])
        self.log_huella = {bot: math.log(max(pr.get(bot, 0.0) / z, 1e-12)) for bot in h["tabla"]}
        self.n_z = 0
        self.contadores = {"manos": 0, "cajas_z": [0] * (len(h["cajas"]) + 1), "preflop_fcr": {"F": 0, "C": 0, "R": 0},
                           "post": {"apuestas": 0, "subidas": 0, "pagos": 0, "pasa": 0, "retiros_ante_apuesta": 0,
                                    "enfrentadas": 0},
                           "showdowns": 0}
        if datos:
            self._cargar(datos)

    # --- Persistencia ---
    def a_dict(self):
        return {"id": self.id, "stats": {n: s.a_dict() for n, s in self.stats.items()}, "log_pi": self.log_pi,
                "log_huella": self.log_huella, "n_z": self.n_z, "contadores": self.contadores}

    def _cargar(self, d):
        for n, v in (d.get("stats") or {}).items():
            if n in self.stats:
                self.stats[n] = Beta(0, 0, v["alfa"], v["beta"], v.get("k", 0), v.get("n", 0))
        for t, v in (d.get("log_pi") or {}).items():
            if t in self.log_pi:
                self.log_pi[t] = v
        for b, v in (d.get("log_huella") or {}).items():
            if b in self.log_huella:
                self.log_huella[b] = v
        self.n_z = d.get("n_z", 0)
        self.contadores.update(d.get("contadores") or {})

    # --- Lectura ---
    def pi(self):
        """Creencia actual sobre su tipo (§2.3), con piso de 0,01 por tipo."""
        return _normalizar(self.log_pi, self.p["piso_pi"])

    def huella(self):
        """Posterior de que sea cada bot del kit o 'propio' (§2.7)."""
        return _normalizar(self.log_huella)

    def prob_conductual(self, nombre="conservador"):
        """Posterior de que el rival sea `nombre` mirando SOLO su comportamiento (para bots sin huella de montos).
        log-odds = prior + evidencia de (a) agresión postflop, (b) VPIP y (c) PFR; cada una es un cociente de
        verosimilitudes binomial entre H1 (es ese bot) y H0 (otro). Con pocas oportunidades devuelve el prior."""
        c = self.p["conductual"][nombre]
        post = self.contadores["post"]
        agresivas = post["apuestas"] + post["subidas"]
        oportunidades = agresivas + post["pagos"] + post["pasa"] + post["retiros_ante_apuesta"]
        if oportunidades < c["min_oportunidades"]:
            return c["prior"]
        lo = math.log(c["prior"] / (1.0 - c["prior"]))
        e, p0 = c["eps_agresion"], c["p_agresion_otros"]
        lo += agresivas * math.log(e / p0) + (oportunidades - agresivas) * math.log((1 - e) / (1 - p0))
        for estad, si, no in (("vpip", c["vpip_si"], c["vpip_no"]), ("pfr", c["pfr_si"], c["pfr_no"])):
            k, n = self.stats[estad].k, self.stats[estad].n
            lo += k * math.log(si / no) + (n - k) * math.log((1 - si) / (1 - no))
        return 1.0 / (1.0 + math.exp(-max(-50.0, min(50.0, lo))))

    def bot_reconocido(self):
        """(bot, probabilidad) si algún bot del kit supera el umbral (0,9): por huella de montos (§2.7) o, para los
        que nunca apuestan (conservador), por comportamiento; si no, None."""
        umbral = self.p["huella"]["umbral"]
        post = self.huella()
        bot = max(post, key=post.get)
        if bot != "propio" and post[bot] >= umbral:
            return bot, post[bot]
        for nombre in self.p["conductual"]:
            pc = self.prob_conductual(nombre)
            if pc >= umbral:
                return nombre, pc
        return None

    def estadistica(self, nombre):
        s = self.stats[nombre]
        return {"p": s.p, "sigma": s.sigma, "n": s.n}

    # --- Escritura (cada una aplica el olvido λ antes de sumar) ---
    def obs_stat(self, nombre, si):
        self.stats[nombre].observar(si, self.p["olvido"]["lambda"])

    def obs_tipo(self, log_verosimilitud):
        """log π_t ← λ·log π_t + log P(a|t) (§2.3)."""
        lam = self.p["olvido"]["lambda"]
        for t in self.log_pi:
            self.log_pi[t] = lam * self.log_pi[t] + log_verosimilitud[t]

    def obs_huella(self, caja):
        """Bayes puro sobre la huella: los bots del kit no cambian de estilo (§2.7)."""
        fila = self.p["huella"]["tabla"]
        for bot in self.log_huella:
            self.log_huella[bot] += math.log(max(fila[bot][caja], 1e-6))
        self.n_z += 1
        self.contadores["cajas_z"][caja] += 1


class Memoria:
    """Rivales por ID, con carga y guardado en disco (un JSON por rival)."""

    def __init__(self, params, directorio=None, persistir=None):
        self.p = params
        self.dir = directorio or params["rivales"].get("dir") or DIR_DEFECTO
        # Si no se dice otra cosa, manda el parámetro rivales.persistir (antes se ignoraba).
        self.persistir = params["rivales"]["persistir"] if persistir is None else persistir
        self._r = {}
        self._sucios = set()

    def _ruta(self, id_):
        seguro = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in id_)
        return os.path.join(self.dir, f"{seguro}.json")

    def rival(self, id_):
        r = self._r.get(id_)
        if r is None:
            datos = None
            if self.persistir:
                try:
                    with open(self._ruta(id_), encoding="utf-8") as f:
                        datos = json.load(f)
                except (OSError, ValueError):
                    datos = None
            r = self._r[id_] = Rival(id_, self.p, datos)
        return r

    def marcar(self, id_):
        self._sucios.add(id_)

    def guardar(self):
        """Escribe los rivales modificados (se llama al terminar cada mano). Nunca lanza."""
        if not self.persistir or not self._sucios:
            self._sucios.clear()
            return
        try:
            os.makedirs(self.dir, exist_ok=True)
            for id_ in list(self._sucios):
                ruta = self._ruta(id_)
                tmp = ruta + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self._r[id_].a_dict(), f)
                os.replace(tmp, ruta)
        except OSError:
            pass
        self._sucios.clear()

    def pi(self, id_):
        return self.rival(id_).pi()


class Observador:
    """Mensajes de la mesa -> estadísticas por rival. Recibe TODOS los mensajes (incluidos los `estado`
    de manos que Bender no juega) y reconstruye cada acción con el pozo y la apuesta del momento."""

    def __init__(self, params, memoria, mi_id=None):
        self.p = params
        self.mem = memoria
        self.mi_id = mi_id
        self.cache = POB.CacheCategorias()
        self._nueva_mano("")

    def _nueva_mano(self, id_mano):
        self.id_mano = id_mano
        self.inicio_visto = False
        self.dealt = []                      # ids que recibieron cartas
        self.n_hist = 0
        self.etapa = "preflop"
        self.pozo, self.apuesta, self.ronda, self.saldo = 0, 0, {}, {}
        self.ultima_z = {}                   # etapa -> z de la última apuesta/subida (la que enfrenta el siguiente)
        self.eventos = []                    # dicts por acción, en orden
        self.comunitarias = []

    # --- Entrada ---
    def al_mensaje(self, msg):
        tipo = msg.get("tipo")
        if tipo == "mano_fin":
            self._fin_mano(msg.get("resultado") or {})
            return
        if tipo not in ("mano_inicio", "estado", "solicitar_accion") or not msg.get("estado"):
            return
        est = EstadoPublico.de_dict(msg["estado"])
        if est.id_mano != self.id_mano:
            self._nueva_mano(est.id_mano)
        if tipo == "mano_inicio" and not self.inicio_visto:
            self.inicio_visto = True
            self.dealt = [j.id for j in est.jugadores if j.en_mano]
            self.pozo, self.apuesta = est.pozo, est.apuesta_actual
            self.ronda = {j.id: j.apuesta_ronda for j in est.jugadores}
            self.saldo = {j.id: j.saldo for j in est.jugadores}
        elif not self.dealt:
            self.dealt = [j.id for j in est.jugadores if j.en_mano]
        self.comunitarias = [C.de_tupla(c) for c in est.comunitarias]
        nuevas = est.historial[self.n_hist:]
        for a in nuevas:
            self._accion(a)
        self.n_hist = len(est.historial)
        # Se vuelve a sincronizar con el estado real (corrige cualquier desvío del modelo)
        if self.inicio_visto or nuevas:
            self.pozo, self.apuesta = est.pozo, est.apuesta_actual
            self.ronda = {j.id: j.apuesta_ronda for j in est.jugadores}
            self.saldo = {j.id: j.saldo for j in est.jugadores}

    # --- Una acción ---
    def _accion(self, a):
        id_, etapa, ac = a.get("id_jugador"), a.get("etapa"), a.get("accion") or {}
        tipo, monto = ac.get("tipo"), ac.get("monto") or 0
        if etapa != self.etapa:                                   # calle nueva: las apuestas de la ronda se reinician
            self.etapa, self.ronda, self.apuesta = etapa, {k: 0 for k in self.ronda}, 0
        r = self.ronda.get(id_, 0)
        saldo = self.saldo.get(id_)
        falta = max(0, self.apuesta - r)                          # lo que le falta para igualar
        z, z_enfrentada, allin = None, self.ultima_z.get(etapa), tipo == "allin"
        enfrentaba = falta > 0
        pago = 0
        if tipo in ("bet", "raise"):
            pago = monto - r
            if saldo is not None and pago >= saldo:
                allin = True                                      # apuesta recortada por el stack: no cuenta para z
            if self.pozo + falta > 0:
                z = (monto - self.apuesta) / (self.pozo + falta)
            self.apuesta = max(self.apuesta, monto)
            self.ultima_z[etapa] = None if (allin or etapa == "preflop") else z
        elif tipo == "allin":
            pago = saldo if saldo is not None else 0
            if r + pago > self.apuesta:
                self.apuesta = r + pago
            self.ultima_z[etapa] = None
        elif tipo == "call":
            pago = min(falta, saldo) if saldo is not None else falta
        if saldo is not None:
            pago = min(pago, saldo)
            self.saldo[id_] = saldo - pago
        self.pozo += pago
        self.ronda[id_] = r + pago

        ev = {"id": id_, "etapa": etapa, "tipo": tipo, "enfrentaba": enfrentaba, "z": z, "z_enfrentada": z_enfrentada,
              "allin": allin, "board": tuple(sorted(self.comunitarias[:CARTAS_DE_CALLE.get(etapa, 0)]))}
        self.eventos.append(ev)
        if id_ != self.mi_id and self.inicio_visto:
            self._aprender_accion(ev)

    def _aprender_accion(self, ev):
        """Lo que se aprende en el momento de la acción (no hace falta esperar al final de la mano)."""
        riv = self.mem.rival(ev["id"])
        c = riv.contadores["post"]
        if ev["etapa"] == "preflop":
            return
        if ev["tipo"] in APUESTAS:
            c["apuestas" if not ev["enfrentaba"] else "subidas"] += 1
            if ev["z"] is not None and not ev["allin"]:
                riv.obs_huella(caja_de_z(ev["z"], self.p["huella"]))          # §2.7
        elif ev["tipo"] == "call":
            c["pagos"] += 1
        elif ev["tipo"] == "check":
            c["pasa"] += 1
        if ev["enfrentaba"]:
            c["enfrentadas"] += 1
            if ev["tipo"] == "fold":
                c["retiros_ante_apuesta"] += 1
            # "Sigue ante una apuesta" (§2.5): chica x <= 0,6, grande x > 0,6
            if ev["z_enfrentada"] is not None and ev["tipo"] in ("fold", "call", "raise", "allin", "bet"):
                chica = ev["z_enfrentada"] <= self.p["beta"]["x_chica_max"]
                riv.obs_stat("sigue_chica" if chica else "sigue_grande", ev["tipo"] != "fold")
        self.mem.marcar(ev["id"])

    # --- Fin de mano ---
    def _fin_mano(self, resultado):
        if not self.inicio_visto and not self.eventos:
            self._nueva_mano("")
            return
        cartas = {i: [C.carta(int(c["rango"]), int(c["palo"])) for c in cs]
                  for i, cs in (resultado.get("mostradas") or {}).items()}
        for id_ in self.dealt:
            if id_ == self.mi_id:
                continue
            riv = self.mem.rival(id_)
            pre = [e for e in self.eventos if e["id"] == id_ and e["etapa"] == "preflop"]
            if self.inicio_visto:
                voluntaria = [e for e in pre if e["tipo"] in ("call", "bet", "raise", "allin")]
                riv.obs_stat("vpip", bool(voluntaria))
                riv.obs_stat("pfr", any(e["tipo"] in APUESTAS for e in pre))
                riv.contadores["manos"] += 1
                # Tipo (§2.3): primera decisión preflop de la mano: F / C / R
                primera = next((e for e in pre if e["tipo"] != "check"), None)
                if primera is not None:
                    letra = "F" if primera["tipo"] == "fold" else ("C" if primera["tipo"] == "call" else "R")
                    riv.contadores["preflop_fcr"][letra] += 1
                    tabla = self.p["preflop_verosimilitud"][letra]
                    riv.obs_tipo({t: math.log(max(tabla[t], 1e-3)) for t in riv.log_pi})
            if id_ in cartas and len(cartas[id_]) == 2:
                self._tipo_con_cartas(riv, id_, tuple(sorted(cartas[id_])))
            self.mem.marcar(id_)
        self.mem.guardar()
        self._nueva_mano("")

    def _tipo_con_cartas(self, riv, id_, combo):
        """Con las cartas a la vista, cada acción postflop del rival actualiza su tipo (§2.2, §2.3)."""
        riv.contadores["showdowns"] += 1
        for e in self.eventos:
            if e["id"] != id_ or e["etapa"] == "preflop" or len(e["board"]) < 3 or e["tipo"] == "fold":
                continue
            if set(combo) & set(e["board"]):
                continue                                              # inconsistente: ignorar
            cat = self.cache.de(combo, e["board"])
            logs = {}
            for t in riv.log_pi:
                pl = POB.plantilla_mezcla({t: 1.0}, self.p)
                pa = POB.prob_apuesta({t: 1.0}, self.p)
                tabla = POB.tabla_de_accion(e["tipo"], e["enfrentaba"], pl, pa)
                if tabla is None:
                    break
                logs[t] = math.log(max(tabla[cat], 1e-3))
            else:
                riv.obs_tipo(logs)
