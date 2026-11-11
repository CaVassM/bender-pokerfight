"""Capa 1 · Cerebro sólido (bender/docs/bender_formulas.tex, §1).

Una decisión sigue siempre estos pasos (cada uno cita su sección):

  1. Modo por stack efectivo S_ef: push/fold, intermedio o profundo (§1.4).
  2. Preflop y nadie subió: se abre con el top % de la posición, a 2,5 bb, o se
     retira. Nunca se entra pagando la ciega (§1.5).
  3. En cualquier otro caso se arma el menú de 5 acciones (retirarse, pasar o
     igualar, x≈1/2, x≈1, all-in; §1.8) y se calcula el EV de cada una:
        EV(retirarse) = 0                        EV(pasar)  = e·P
        EV(igualar)   = e·(P+C) − C   (§1.6)
        EV(apuesta)   = f·P + (1−f)·[e'·(P+A+A') − A]   (§1.9)
     con e = equity contra el rango del rival (§1.3), e' = equity si le pagan,
     f = Π(1−c_i) (§1.7) y c_i sacado del rango del rival (§3.3 θ_base; si no hay rango,
     c(x) de población, §1.7).
  4. Se descartan acciones (multiway y compromiso) y se elige el mayor EV, con
     una mezcla para no ser predecible (§1.11).
  5. Perilla de riesgo del torneo (§1.12) con g = 0 por ahora.

Cada decisión devuelve (acción, motivo, info): `info` trae todo lo que hace falta
para entender el porqué (modo, equities con su N y tiempo, c_i, f, la tabla de EV
con su fórmula y los descartes), y bot.py lo escribe en el registro.
"""

import random

import cartas as C
import poblacion as POB
import rangos as R
from equity import estimar, t_max_de_reloj
from estado import posiciones


def modo_de(s_ef_bb, p):
    """§1.4: push/fold si S_ef <= 15 bb, intermedio si <= 25 bb, profundo si más."""
    if s_ef_bb <= p["push_fold_bb"]:
        return "push_fold"
    if s_ef_bb <= p["intermedio_bb"]:
        return "intermedio"
    return "profundo"


def tipo_de_apuesta(e_prima, p):
    """§1.11: valor (e' >= 0,50), semi-farol (0,25 <= e' < 0,50) o farol."""
    if e_prima >= p["umbral_valor"]:
        return "valor"
    if e_prima >= p["umbral_semifarol"]:
        return "semi-farol"
    return "farol"


def ev_pasar(e, P):
    """EV(pasar) = e·P."""
    return e * P


def ev_igualar(e, P, C, saldo, delta=0.0):
    """§1.6 EV(igualar) = e·(P+C) − C. Si no alcanza el saldo, se iguala con lo que hay y
    la parte de la apuesta ajena que no se puede cubrir vuelve a su dueño. `delta` es el
    margen de equity de §1.12 (e_min + δ), que se resta como δ·(P+C)."""
    c_ef = min(C, saldo)
    p_ef = P - (C - c_ef)
    return e * (p_ef + c_ef) - c_ef - delta * (p_ef + c_ef)


def ev_apuesta(f, P, e_prima, A, A_prima):
    """§1.9 EV(apuesta) = f·P + (1−f)·[e'·(P+A+A') − A]."""
    return f * P + (1.0 - f) * (e_prima * (P + A + A_prima) - A)


class Capa1:
    def __init__(self, params, rng=None):
        self.p = params
        self.rng = rng or random.Random(params["capa1"]["semilla"])       # para el Monte Carlo
        self.rng_mezcla = random.Random(self.rng.random())                # aparte, para la mezcla de §1.11
        self.cache = POB.CacheCategorias()
        self._c_medio = {}
        self._id_mano = None

    # ------------------------------------------------------------------ entrada
    def decidir(self, turno, mesa):
        """Devuelve (acción, motivo, info). `mesa` aporta manos_mesa y segundos_mesa (reloj §1.2)."""
        p = self.p
        if turno.estado.id_mano != self._id_mano:
            self._id_mano = turno.estado.id_mano
            self.cache = POB.CacheCategorias()          # la caché de categorías vive una mano

        mano = [C.de_tupla(c) for c in turno.mano]
        board = [C.de_tupla(c) for c in turno.comunitarias]
        s_ef = turno.stack_efectivo_bb()
        modo = modo_de(s_ef, p["modo"])
        info = {"modo": modo, "s_ef_bb": round(s_ef, 1), "posicion": turno.mi_posicion}
        preflop = not board
        hubo_subida = turno.estado.apuesta_actual > turno.bb

        if preflop and not hubo_subida and turno.C > 0 and modo != "push_fold":
            return self._apertura(turno, mano, info)
        return self._menu(turno, mesa, mano, board, modo, info, pushfold=(preflop and modo == "push_fold"))

    # ------------------------------------------------------------------ §1.5
    def _apertura(self, turno, mano, info):
        """Nadie subió: se abre con rank(h) <= top_pos % a 2,5 bb, o se retira (sin limp)."""
        p = self.p
        tabla = p["apertura"]["top_pos"]
        clave = POB.clave_posicion(turno.mi_posicion)
        top = tabla.get(clave, tabla["CO"])
        clase = R.clase_de_combo(*sorted(mano))
        abre = clase in set(R.clases_top(top))
        info.update({"decision": "apertura", "clase": clase, "top_pos": top, "abre": abre})
        if abre:
            monto = int(round(p["apertura"]["tamano_bb"] * turno.bb))
            return turno.apostar(monto), f"apertura {clase} desde {turno.mi_posicion} (top {top}%) a {p['apertura']['tamano_bb']} bb", info
        return {"tipo": "fold"}, f"{clase} fuera del top {top}% de {turno.mi_posicion}: me retiro (sin limp)", info

    # ------------------------------------------------------------------ rangos y equity
    def _rangos_rivales(self, turno, mano, board):
        """Rango vivo de cada rival que sigue en la mano (modelo de población)."""
        muertas = C.mascara(mano + board)
        if not self.p["capa1"]["rangos_poblacion"]:
            return {r.id: R.rango_alazar(muertas) for r in turno.rivales}
        evs = POB.eventos(turno.estado.historial)
        pos = posiciones(turno.estado)
        return {r.id: POB.rango_de_rival(r.id, pos.get(r.id, ""), evs, board, mano, self.p, self.cache)
                for r in turno.rivales}

    def _equity(self, mano, board, rangos, umbrales, mesa, t_max):
        res = estimar(mano, board, rangos, self.p["reloj"], umbrales=umbrales, manos_jugadas=mesa.manos_mesa,
                      segundos_mesa=mesa.segundos_mesa, rng=self.rng, t_max=t_max)
        if res.imposible:
            # Rangos que no pueden convivir (cartas muertas): se cae a manos al azar.
            muertas = C.mascara(mano + board)
            res = estimar(mano, board, [R.rango_alazar(muertas) for _ in rangos], self.p["reloj"], umbrales=umbrales,
                          manos_jugadas=mesa.manos_mesa, segundos_mesa=mesa.segundos_mesa, rng=self.rng, t_max=t_max)
        return res

    @staticmethod
    def _resumen_equity(res):
        return {"e": round(res.e, 4), "n": res.n, "sigma": round(res.sigma, 4), "tiempo_s": round(res.tiempo_s, 4),
                "parada": res.parada, "e_ref": None if res.e_ref is None else round(res.e_ref, 4)}

    # ------------------------------------------------------------------ §1.6 a §1.11
    def _menu(self, turno, mesa, mano, board, modo, info, pushfold):
        p = self.p
        P, C_, bb = turno.P, turno.C, turno.bb
        yo = turno.yo
        preflop = not board
        rivales = turno.rivales
        responden = [r for r in rivales if not r.allin and r.saldo > 0]
        info["decision"] = "push/fold" if pushfold else "menu"
        info["P"], info["C"] = P, C_
        self._c_medio = {}                      # c_{1/2} de cada rival en esta decisión (postflop)

        if not rivales:
            return turno.pagar(), "sin rivales en la mano", info

        # --- Candidatos del menú de 5 acciones (§1.8) ---
        candidatos = []
        if turno.puede("fold") and not (C_ == 0 and turno.puede("check")):
            candidatos.append({"nombre": "retirarse", "accion": {"tipo": "fold"}, "clase": "fold"})
        pasiva = turno.pagar()
        if pasiva["tipo"] == "check":
            candidatos.append({"nombre": "pasar", "accion": pasiva, "clase": "check"})
        elif pasiva["tipo"] in ("call", "allin") and not (pushfold and responden and pasiva["tipo"] == "call"):
            candidatos.append({"nombre": "igualar" if pasiva["tipo"] == "call" else "igualar (all-in)",
                               "accion": pasiva, "clase": "call"})
        vistos = {("allin" if a["accion"]["tipo"] == "allin" else a["accion"]["tipo"], a["accion"].get("monto"))
                  for a in candidatos}
        if responden and (turno.puede("bet") or turno.puede("raise") or turno.puede("allin")):
            tamanos = [] if pushfold else list(p["menu"]["tamanos"])
            acciones = [(f"x={x}", turno.apostar_pozo(x)) for x in tamanos] + [("all-in", turno.todo())]
            for nombre, acc in acciones:
                if acc["tipo"] not in ("bet", "raise", "allin"):
                    continue
                if acc["tipo"] == "allin" and turno.techo <= turno.estado.apuesta_actual:
                    continue                         # ese all-in es solo un call corto: ya está arriba
                clave = (acc["tipo"], acc.get("monto"))
                if clave in vistos:
                    continue
                vistos.add(clave)
                candidatos.append({"nombre": nombre, "accion": acc, "clase": "apuesta"})

        # --- Rangos de los rivales y equity ---
        rangos = self._rangos_rivales(turno, mano, board)
        info["rangos"] = {i: {"combos": len(r), "pct": round(100.0 * len(r) / 1326, 1)} for i, r in rangos.items()}
        t_max = t_max_de_reloj(p["reloj"], mesa.manos_mesa, mesa.segundos_mesa)
        info["t_max"] = round(t_max, 3)

        e = None
        if any(c["clase"] in ("check", "call") for c in candidatos):
            umbrales = [p["decision"]["umbral_semifarol"], p["decision"]["umbral_valor"]]
            if C_ > 0:
                umbrales.append(C_ / (P + C_))
            res = self._equity(mano, board, [rangos[r.id] for r in rivales], umbrales, mesa, t_max / 2)
            e = res.e
            info["equity"] = self._resumen_equity(res)

        apuestas = [c for c in candidatos if c["clase"] == "apuesta"]
        big, ep_cache = None, {}
        if apuestas:
            big = max(responden, key=lambda r: r.saldo + r.apuesta_ronda)
        info["equities_si_pagan"] = []

        delta = 0.0
        if C_ > yo.saldo / 3.0:                                     # §1.12: solo calls que arriesgan mucho stack
            delta = p["riesgo"]["delta_max"] * p["riesgo"]["g"]

        # --- EV de cada candidato ---
        for c in candidatos:
            acc = c["accion"]
            if c["clase"] == "fold":
                c["ev"], c["formula"] = 0.0, "EV(retirarse) = 0"
            elif c["clase"] == "check":
                c["ev"] = ev_pasar(e, P)
                c["formula"] = f"e·P = {e:.3f}·{P}"
            elif c["clase"] == "call":
                c["ev"] = ev_igualar(e, P, C_, yo.saldo, delta)
                c["formula"] = f"e·(P+C)−C = {e:.3f}·({P}+{C_})−{C_}" + (f" −δ·(P+C) con δ={delta:.3f}" if delta else "")
            else:
                monto = acc["monto"] if acc["tipo"] != "allin" else turno.techo
                A = monto - yo.apuesta_ronda
                x = turno.fraccion_de_monto(monto)
                # Si el rival más grande no puede cubrir todo, la parte sobrante vuelve a Bender.
                tope_cubierto = big.saldo + big.apuesta_ronda - yo.apuesta_ronda
                A_ef = max(0, min(A, tope_cubierto))
                A_p = max(0, min(monto - big.apuesta_ronda, big.saldo))
                cs = {r.id: self._c_rival(r, x, pushfold, rangos[r.id], board) for r in responden}
                f = 1.0
                for v in cs.values():
                    f *= (1.0 - v)
                # e' depende del tamaño: quien paga una apuesta grande es solo la parte fuerte de su rango.
                e_prima = self._e_prima(mesa, mano, board, rangos, responden, cs, c["nombre"], t_max / (1 + len(apuestas)),
                                        ep_cache, info)
                c["e_prima"] = e_prima
                c["ev"] = ev_apuesta(f, P, e_prima, A_ef, A_p)
                c["x"], c["A"], c["A_prima"], c["f"], c["c"] = round(x, 3), A_ef, A_p, round(f, 4), {k: round(v, 3) for k, v in cs.items()}
                c["tipo_apuesta"] = tipo_de_apuesta(e_prima, p["decision"])
                c["formula"] = (f"f·P+(1−f)·[e'·(P+A+A')−A] con f={f:.3f} P={P} e'={e_prima:.3f} A={A_ef} A'={A_p} (x={x:.2f})")

        # --- Descartes (§1.11) ---
        d = p["decision"]
        for c in candidatos:
            c["descartada"] = None
            if c["clase"] == "apuesta":
                ep = c["e_prima"]
                if len(rivales) >= d["multiway_rivales"] and ep < d["umbral_valor"]:
                    c["descartada"] = f"multiway: {len(rivales)} rivales y e'={ep:.2f}<{d['umbral_valor']}"
                if ep < d["umbral_valor"]:
                    # Variantes opcionales (apagadas por defecto: no son del .tex; ver params.py)
                    if d["allin_profundo_solo_valor"] and modo == "profundo" and c["accion"]["tipo"] == "allin":
                        c["descartada"] = f"variante: all-in en modo profundo solo con valor (e'={ep:.2f})"
                    if d["solo_valor_sobre_apuesta"] and C_ > 0:
                        c["descartada"] = f"variante: subir sobre una apuesta solo con valor (e'={ep:.2f})"
            if modo != "profundo" and c["clase"] in ("call", "apuesta") and c["accion"]["tipo"] != "allin":
                coste = C_ if c["clase"] == "call" else c["A"]
                if coste > turno.techo * d["compromiso_fraccion"]:
                    c["descartada"] = f"compromiso: cuesta {coste} > {d['compromiso_fraccion']:.2f} del stack ({turno.techo})"

        vivos = [c for c in candidatos if not c["descartada"]]
        if not vivos:                                   # nunca quedarse sin acción
            vivos = [c for c in candidatos if c["clase"] in ("fold", "check", "call")] or candidatos
        vivos.sort(key=lambda c: -c["ev"])
        elegido, mezcla = vivos[0], False
        if len(vivos) > 1:
            a, b = vivos[0], vivos[1]
            if (a["ev"] - b["ev"] < d["mezcla_ev_frac"] * max(P, bb) and b["ev"] >= 0
                    and a["clase"] != "fold" and b["clase"] != "fold" and self.rng_mezcla.random() < d["mezcla_prob"]):
                elegido, mezcla = b, True

        info["tabla_ev"] = [{"accion": c["nombre"], "tipo": c["accion"]["tipo"], "monto": c["accion"].get("monto"),
                             "ev": round(c["ev"], 1), "formula": c["formula"], "descartada": c["descartada"],
                             **({k: c[k] for k in ("x", "A", "A_prima", "f", "c", "e_prima", "tipo_apuesta") if k in c})}
                            for c in candidatos]
        info["elegida"], info["mezcla"] = elegido["nombre"], mezcla
        motivo = f"{elegido['nombre']} (EV {elegido['ev']:+.0f})" + (" [mezcla con la 2.ª mejor]" if mezcla else "")
        return elegido["accion"], motivo, info

    # ------------------------------------------------------------------ c_i y e'
    def _c_rival(self, rival, x, pushfold, rango, board):
        """c_i, la probabilidad de que el rival siga ante una apuesta de tamaño x.

        §3.3: θ_base de c_i es el c que sale del RANGO y las plantillas (§2.1); solo sin rango se
        usa c(x) de población (§1.7). Postflop: c = Σ w·P(sigue|h)/Σ w (a x≈1/2) escalado a x.
        Preflop: la parte del rango que está dentro del umbral de fuerza de c_pob(x). En push/fold:
        0,385 (rango de pago Nash a 10 bb, §1.10)."""
        p = self.p
        if pushfold:
            return p["pushfold"]["c_pago"]
        ya = rival.apuesta_ronda > 0
        if rango is None or rango.vacio() or not p["capa1"]["rangos_poblacion"]:
            return POB.c_poblacion(x, ya, p["pob"])
        if not board:
            return POB.c_de_rango_preflop(rango, x, ya, p["pob"])
        if rival.id not in self._c_medio:
            plantilla = POB.plantilla_mezcla(p["capa1"]["pi_defecto"], p)
            self._c_medio[rival.id] = POB.c_sigue(rango, board, plantilla, self.cache)
        return POB.c_de_rango_postflop(self._c_medio[rival.id], x, ya, p["pob"])

    def _e_prima(self, mesa, mano, board, rangos, responden, cs, nombre, t_max, cache, info):
        """e' = equity si le pagan ESTA apuesta (§1.9), contra el rango de pago de quienes pagarían.

        Depende del tamaño: ante una apuesta grande solo paga la parte fuerte del rango (c bajo),
        y contra eso la equity de Bender es menor. `cs` son los c_i de esta apuesta.
        Aproximación propia (el .tex no fija el multiway): pagan los n_pago rivales con mayor c_i,
        con n_pago = max(1, redondeo(Σ c_i)). Preflop cada pagador usa su fracción c_i más fuerte;
        postflop su rango se reajusta con P(paga|categoría) de la plantilla (§2.1), que ya está
        calibrada para x≈1/2 y no cambia con el tamaño. Se memoriza por (pagadores, c_i) para no
        repetir la simulación cuando dos tamaños dan el mismo rango de pago.
        """
        p = self.p
        n_pago = max(1, min(len(responden), int(round(sum(cs.values())))))
        pagan = sorted(responden, key=lambda r: -cs[r.id])[:n_pago]
        clave = (tuple(r.id for r in pagan), None if board else tuple(round(cs[r.id], 2) for r in pagan))
        if clave in cache:
            return cache[clave]
        plantilla = POB.plantilla_mezcla(p["capa1"]["pi_defecto"], p)
        rangos_pago = []
        for r in pagan:
            base = rangos[r.id]
            if board:
                rp = POB.rango_de_pago(base, board, plantilla, self.cache, p["rango"]["piso"]) if not base.vacio() else base
            else:
                rp = POB.top_fraccion(base, cs[r.id])
            rangos_pago.append(rp)
        umbrales = [p["decision"]["umbral_semifarol"], p["decision"]["umbral_valor"]]
        res = self._equity(mano, board, rangos_pago, umbrales, mesa, t_max)
        resumen = self._resumen_equity(res)
        resumen.update({"para": nombre, "pagan": [r.id for r in pagan]})
        info["equities_si_pagan"].append(resumen)
        info.setdefault("equity_si_pagan", resumen)           # la primera, por compatibilidad
        cache[clave] = res.e
        return res.e
