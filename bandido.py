"""Capa 3, paso 2: bandido ONLINE sobre brazos de parámetros (fórmulas en bender/docs/bender_formulas_rl.tex, Parte 2).

Antes de cada mano (en el `mano_inicio`) elige UN brazo —una sobreescritura parcial de los parámetros— y la aplica EN SITIO sobre el
mismo diccionario de parámetros que comparten la Capa 1, la Capa 2 y la explotación (todas lo leen en el momento de decidir, así que no
hace falta reconstruir nada). Al empezar la mano siguiente liquida la recompensa de la anterior:

    r = ln(S_fin + K0) − ln(S_ini + K0)      (S_ini y S_fin = fichas al empezar la mano y al empezar la siguiente; K0 fijo)

El valor de cada brazo se aprende por rival (ID), por tipo de rival y global, y se mezcla con shrinkage jerárquico:

    Q_tipo  = (n_t·Q_t + s·Q_global) / (n_t + s)        Q_rival = (n_r·Q_r + s·Q_tipo) / (n_r + s)

Con pocos datos del rival manda el tipo, y con pocos del tipo, el global. Los conteos y las sumas llevan descuento γ por mano.
La recompensa se normaliza con una desviación estándar móvil (z = r / σ̂) para que el bono de UCB y el softmax de Exp3 tengan escala.
Selectores: "ucb" (D-UCB: Q_hand(a) + c·sqrt(ln N / n_a)), "exp3" (pesos exponenciales sobre la ganancia acumulada estimada con el
estimador ponderado 1/p de Exp3, con piso de probabilidad `exp3_p_min` por brazo) y "fijo" (siempre `brazo_inicial`, para pruebas).
Sin explorar cuando todos los rivales de la mano son bots del kit reconocidos: se juega el brazo de mayor Q_hand (empates: `brazo_inicial`).
Cada decisión del bandido y cada recompensa quedan en el log (`bandido`, `bandido_recompensa`) con s, Q_rival, Q_tipo y Q_global.
"""

import copy
import json
import math
import os
import random


def _poner(dst, src, omitir=()):
    """Copia `src` sobre `dst` EN SITIO (los diccionarios anidados conservan su identidad)."""
    for k, v in src.items():
        if k in omitir:
            continue
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _poner(dst[k], v)
        else:
            dst[k] = copy.deepcopy(v)


class Bandido:
    def __init__(self, params, registro=None, memoria=None, rng=None):
        self.params = params
        self.cfg = params["bandido"]
        self.registro = registro
        self.memoria = memoria
        self.rng = rng or random.Random(0xB0)
        cfg = self.cfg
        self.orden = list(cfg["orden"])
        if cfg["brazo_inicial"] not in self.orden or any(a not in cfg["brazos"] for a in self.orden):
            raise ValueError("bandido: `orden` y `brazo_inicial` deben ser brazos de `brazos`")
        if cfg["selector"] not in ("ucb", "exp3", "fijo"):
            raise ValueError(f"bandido: selector desconocido {cfg['selector']!r}")
        self.base = copy.deepcopy(params)                 # los valores base (brazo "base" = lo que traía el proceso)
        from params import _mezclar                       # una clave mal escrita en un brazo no puede ignorarse en silencio
        for a in self.orden:
            _mezclar(copy.deepcopy(params), copy.deepcopy(cfg["brazos"][a]))
        self.actual = None
        self.t = 0                                        # manos liquidadas: reloj del descuento
        self.datos = {"rival": {}, "tipo": {}, "global": {}}      # nivel -> clave -> brazo -> [n, suma, t_ult]
        self.m2 = [0.0, 0.0, 0]                           # [Σ r² con descuento, peso, t_ult]: escala de la recompensa
        self.pendiente = None
        self._sin_guardar = 0
        self._cargar()

    # ------------------------------------------------------------------ estado (con descuento perezoso)
    @property
    def q0(self):
        """Valor de un brazo sin datos: 0 en unidades z (UCB); 0,5 en unidades g de [0, 1] (Exp3)."""
        return 0.5 if self.cfg["selector"] == "exp3" else 0.0

    def _leer(self, nivel, clave, brazo):
        e = self.datos[nivel].get(clave, {}).get(brazo)
        if e is None:
            return 0.0, 0.0
        f = self.cfg["descuento"] ** (self.t - e[2])
        return e[0] * f, e[1] * f

    def _sumar(self, nivel, clave, brazo, dn, ds):
        e = self.datos[nivel].setdefault(clave, {}).setdefault(brazo, [0.0, 0.0, self.t])
        f = self.cfg["descuento"] ** (self.t - e[2])
        e[0], e[1], e[2] = e[0] * f + dn, e[1] * f + ds, self.t

    def _q(self, nivel, clave, brazo):
        n, s = self._leer(nivel, clave, brazo)
        return n, (s / n if n > 1e-9 else self.q0)

    def q_jerarquico(self, id_rival, tipo, brazo):
        """(Q_rival, detalle): shrinkage rival -> tipo -> global con peso s del nivel de arriba."""
        s = self.cfg["s_shrink"]
        n_g, q_g = self._q("global", "g", brazo)
        n_t, q_t0 = self._q("tipo", tipo, brazo)
        q_t = (n_t * q_t0 + s * q_g) / (n_t + s)
        n_r, q_r0 = self._q("rival", id_rival, brazo)
        q_r = (n_r * q_r0 + s * q_t) / (n_r + s)
        return q_r, {"n_r": round(n_r, 2), "Q_r": round(q_r0, 4), "n_t": round(n_t, 2), "Q_t": round(q_t0, 4),
                     "Q_tipo": round(q_t, 4), "n_g": round(n_g, 2), "Q_g": round(q_g, 4), "Q_rival": round(q_r, 4)}

    def sigma(self):
        c = self.cfg
        f = c["descuento"] ** (self.t - self.m2[2])
        return math.sqrt((c["n_sigma0"] * c["sigma0"] ** 2 + self.m2[0] * f) / (c["n_sigma0"] + self.m2[1] * f))

    # ------------------------------------------------------------------ rivales de la mano
    def _rival(self, id_):
        """(clave de tipo, reconocido): bot del kit reconocido por la huella (§2.7) o el tipo dominante de π (§2.3)."""
        if self.memoria is None:
            return "tipo:?", False
        riv = self.memoria.rival(id_)
        rec = riv.bot_reconocido()
        if rec:
            return "bot:" + rec[0], True
        pi = riv.pi()
        return "tipo:" + max(pi, key=pi.get), False

    # ------------------------------------------------------------------ elegir
    def elegir(self, ids, tipos, reconocidos):
        """(brazo, prob del brazo elegido o None, info para el log)."""
        cfg, arms = self.cfg, self.orden
        sel = cfg["selector"]
        if ids:
            piezas = {a: [self.q_jerarquico(i, tipos[i], a) for i in ids] for a in arms}
            qh = {a: sum(p[0] for p in piezas[a]) / len(ids) for a in arms}
        else:
            piezas = {a: [] for a in arms}
            qh = {a: self._q("global", "g", a)[1] for a in arms}
        explorar = cfg["explorar_vs_kit"] or not (ids and all(reconocidos[i] for i in ids))
        prob = None
        indice = dict(qh)
        if sel == "fijo":
            brazo, explorar = cfg["brazo_inicial"], False
        elif not explorar:
            brazo = self._greedy(qh)
        elif sel == "ucb":
            n_a = {a: self._q("global", "g", a)[0] for a in arms}
            sin_probar = [a for a in arms if n_a[a] < 1e-9]
            if sin_probar:
                brazo = cfg["brazo_inicial"] if cfg["brazo_inicial"] in sin_probar else sin_probar[0]
            else:
                total = sum(n_a.values())
                indice = {a: qh[a] + cfg["c_ucb"] * math.sqrt(math.log(max(2.0, total)) / n_a[a]) for a in arms}
                brazo = self._greedy(indice)
        else:                                                              # exp3
            k, pmin = len(arms), cfg["exp3_p_min"]
            n_pasos = self._q("global", "g", arms[0])[0]                   # pasos efectivos: todos los brazos suman 1 por paso
            horizonte = min(1000.0, 1.0 / max(1e-9, 1.0 - cfg["descuento"]))      # T de la tasa teórica de Exp3 (ventana del descuento)
            eta = math.sqrt(2.0 * math.log(k) / (k * horizonte)) if k > 1 else 0.0
            l = {a: eta * n_pasos * qh[a] for a in arms}
            mx = max(l.values())
            w = {a: math.exp(l[a] - mx) for a in arms}
            z = sum(w.values())
            p = {a: pmin + (1.0 - k * pmin) * w[a] / z for a in arms}
            u, acum = self.rng.random(), 0.0
            brazo = arms[-1]
            for a in arms:
                acum += p[a]
                if u < acum:
                    brazo = a
                    break
            prob, indice = p[brazo], p
        info = {"selector": sel, "explorar": explorar, "Q_hand": {a: round(qh[a], 4) for a in arms},
                "indice": {a: round(v, 4) for a, v in indice.items()}, "s": cfg["s_shrink"], "sigma": round(self.sigma(), 5),
                "rivales": [{"id": i, "tipo": tipos[i], "kit": reconocidos[i],
                             "por_brazo": {a: piezas[a][j][1] for a in arms}} for j, i in enumerate(ids)]}
        return brazo, prob, info

    def _greedy(self, valores):
        """Brazo de mayor valor; los empates (con tolerancia) los gana `brazo_inicial`, luego el orden."""
        mejor = max(valores.values())
        empatan = [a for a in self.orden if valores[a] >= mejor - 1e-12]
        return self.cfg["brazo_inicial"] if self.cfg["brazo_inicial"] in empatan else empatan[0]

    # ------------------------------------------------------------------ aplicar
    def aplicar(self, brazo):
        if brazo == self.actual:
            return
        _poner(self.params, self.base, omitir=("bandido",))
        _poner(self.params, self.cfg["brazos"][brazo])
        self.actual = brazo

    # ------------------------------------------------------------------ ciclo de una mano
    def nueva_mano(self, estado, mi_id, stacks0):
        """Liquida la mano anterior con las fichas de ahora y elige el brazo de la que empieza."""
        s0 = (stacks0 or {}).get(mi_id)
        if self.pendiente is not None and s0 is not None:
            self.liquidar(s0)
        self.pendiente = None
        if s0 is None:                                                     # Bender no juega esta mano: nada que elegir
            return
        ids = [j.id for j in estado.jugadores if j.en_mano and j.id != mi_id]
        tipos, rec = {}, {}
        for i in ids:
            tipos[i], rec[i] = self._rival(i)
        brazo, prob, info = self.elegir(ids, tipos, rec)
        self.aplicar(brazo)
        self.pendiente = {"id_mano": estado.id_mano, "brazo": brazo, "prob": prob, "ids": ids, "tipos": tipos,
                          "explorar": info["explorar"], "S0": s0}
        if self.registro is not None:
            self.registro.escribir("bandido", id_mano=estado.id_mano, brazo=brazo, prob=None if prob is None else round(prob, 4),
                                   S0=s0, **info)

    def liquidar(self, s_fin):
        pen, cfg = self.pendiente, self.cfg
        k0 = cfg["K_recompensa"]
        r = math.log(s_fin + k0) - math.log(pen["S0"] + k0)
        z = r / self.sigma()
        # escala de la recompensa: media móvil de r² con el mismo descuento
        f = cfg["descuento"] ** (self.t - self.m2[2])
        self.m2 = [self.m2[0] * f + r * r, self.m2[1] * f + 1.0, self.t]
        a = pen["brazo"]
        llaves = [("global", "g")] + [("tipo", t) for t in sorted(set(pen["tipos"].values()))] + [("rival", i) for i in pen["ids"]]
        if cfg["selector"] == "exp3":
            if pen["prob"] is not None:                                    # sin exploración no hay probabilidad: no se aprende
                g = (max(-3.0, min(3.0, z)) + 3.0) / 6.0                   # ganancia en [0, 1]
                xhat = g / pen["prob"]                                     # estimador ponderado de Exp3
                for nivel, clave in llaves:
                    for a2 in self.orden:
                        self._sumar(nivel, clave, a2, 1.0, xhat if a2 == a else 0.0)
        else:
            for nivel, clave in llaves:
                self._sumar(nivel, clave, a, 1.0, z)
        self.t += 1
        if self.registro is not None:
            self.registro.escribir("bandido_recompensa", id_mano=pen["id_mano"], brazo=a, S0=pen["S0"], S1=s_fin,
                                   r=round(r, 6), z=round(z, 4), sigma=round(self.sigma(), 5))
        self._sin_guardar += 1
        if self._sin_guardar >= 10:
            self.guardar()

    # ------------------------------------------------------------------ persistencia
    def _ruta(self):
        carpeta = self.params["rivales"].get("dir")
        if not carpeta or not self.cfg["persistir"]:
            return None
        return os.path.join(carpeta, "bandido.json")

    def guardar(self):
        ruta = self._ruta()
        self._sin_guardar = 0
        if ruta is None:
            return
        try:
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            tmp = ruta + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"selector": self.cfg["selector"], "orden": self.orden, "t": self.t, "datos": self.datos, "m2": self.m2}, f)
            os.replace(tmp, ruta)
        except OSError:
            pass                                                           # un fallo de disco nunca tumba una decisión

    def _cargar(self):
        ruta = self._ruta()
        if ruta is None or not os.path.exists(ruta):
            return
        try:
            with open(ruta, encoding="utf-8") as f:
                d = json.load(f)
            if d.get("selector") == self.cfg["selector"] and d.get("orden") == self.orden:
                self.t, self.datos, self.m2 = d["t"], d["datos"], d["m2"]
        except (OSError, ValueError, KeyError):
            pass
