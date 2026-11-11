"""Parámetros ajustables de Bender (tabla §4 de bender/docs/bender_formulas.tex).

Todo lo que la Capa 3 (RL) va a afinar vive aquí, en un solo diccionario, con
los valores iniciales del .tex. Se pueden sobreescribir con `-params archivo.json`:
el JSON se mezcla (merge profundo) sobre estos valores, y una clave que no
exista aquí hace fallar la carga (igual que la arena con sus configs: un
parámetro mal escrito no debe ignorarse en silencio).
"""

import copy
import json

PARAMS = {
    # --- §1.2 Reloj adaptativo --------------------------------------------------
    "reloj": {
        "n_min": 2000,           # N_min: simulaciones mínimas antes de poder parar
        "eps_obj": 0.005,        # ε_obj: precisión suficiente (0,5 puntos de equity)
        "k": 3.0,                # k: σ_e de distancia al umbral que bastan para parar
        "t_tope": 1.5,           # T_tope: tope absoluto por decisión, en segundos
        "eta": 0.5,              # η: fracción de su parte justa del reloj de la mesa
        "t_mesa": 360.0,         # segundos que dura una mesa (6 min)
        "manos_mesa": 50,        # manos por mesa
        "decisiones_por_mano": 2.5,   # estimación de decisiones de Bender por mano
        "revisar_cada": 64,      # cada cuántas simulaciones se mira el reloj
    },
    # --- §1.4 Modos por stack efectivo (en bb) -----------------------------------
    "modo": {"push_fold_bb": 15, "intermedio_bb": 25},
    # --- §1.5 Apertura preflop ----------------------------------------------------
    "apertura": {
        "tamano_bb": 2.5,
        # top % de manos que abre cada posición (con 5 jugadores no hay UTG)
        "top_pos": {"UTG": 14.3, "HJ": 18.9, "CO": 25.5, "BTN": 43.3, "SB": 33.0, "BTN_SB_HU": 70.0},
    },
    # --- §1.7 Fold equity de población: c(x) = a / (1 + b·x) (+extra si ya puso fichas)
    "pob": {"a": 0.65, "b": 0.55, "extra_ya_puso": 0.12, "tope": 0.9},
    # --- §1.8 Menú de tamaños (fracción del pozo) ---------------------------------
    "menu": {"tamanos": [0.5, 1.0]},
    # --- §1.10 Push/fold (Nash a 10 bb, heads-up) ---------------------------------
    "pushfold": {"top_push_sb": 56.6, "top_pago_bb": 38.5, "c_pago": 0.385},
    # --- §1.11 Reglas de decisión -------------------------------------------------
    "decision": {
        "umbral_valor": 0.50,        # e' >= 0,50 -> apuesta de valor
        "umbral_semifarol": 0.25,    # 0,25 <= e' < 0,50 -> semi-farol; menos -> farol
        "multiway_rivales": 3,       # con >= 3 rivales y e' < 0,50 se descartan apuestas
        "compromiso_fraccion": 1 / 3,   # modo intermedio: tope de stack por call/subida
        "mezcla_ev_frac": 0.02,      # |EV1-EV2| < 0,02·max(P, bb) activa la mezcla
        "mezcla_prob": 0.35,         # probabilidad de elegir la segunda mejor
    },
    # --- §1.12 Perilla de riesgo del torneo ---------------------------------------
    "riesgo": {"delta_max": 0.08, "g": 0.0},   # g=0 por ahora (lo define la Capa 3)
    # --- §2.1 Rango ---------------------------------------------------------------
    "rango": {"piso": 0.02},
    # --- §2.2 Plantillas (ret, paga, sube) por categoría --------------------------
    # "promedio" es también la fila del TAG.
    "plantillas": {
        "promedio": {"fuerte": [.05, .55, .40], "media": [.35, .60, .05], "proyecto": [.25, .60, .15], "aire": [.85, .07, .08]},
        "nit":      {"fuerte": [.05, .65, .30], "media": [.50, .48, .02], "proyecto": [.55, .42, .03], "aire": [.93, .05, .02]},
        "station":  {"fuerte": [.02, .88, .10], "media": [.10, .88, .02], "proyecto": [.10, .85, .05], "aire": [.30, .68, .02]},
        "maniaco":  {"fuerte": [.02, .38, .60], "media": [.15, .55, .30], "proyecto": [.10, .45, .45], "aire": [.40, .25, .35]},
        "aleatorio": {c: [1 / 3, 1 / 3, 1 / 3] for c in ("fuerte", "media", "proyecto", "aire")},
    },
    # P(apuesta | categoría) cuando nadie apostó (rival promedio) y su multiplicador por tipo
    "prob_apuesta": {
        "base": {"fuerte": .65, "media": .35, "proyecto": .45, "aire": .25},
        "mult": {"nit": 0.7, "station": 0.6, "maniaco": 1.5, "tag": 1.0},
        "tope": 0.95,
        "aleatorio": 0.50,
    },
    # --- §2.3 Tipos de rival ------------------------------------------------------
    "tipos": ["nit", "tag", "station", "maniaco", "aleatorio"],
    "prior_tipos": {"nit": .25, "tag": .25, "station": .20, "maniaco": .15, "aleatorio": .15},
    "piso_pi": 0.01,
    # P(accion | tipo) preflop por mano: F se retira, C entra pagando, R entra subiendo
    "preflop_verosimilitud": {
        "F": {"nit": .88, "tag": .78, "station": .45, "maniaco": .35, "aleatorio": .33},
        "C": {"nit": .04, "tag": .06, "station": .50, "maniaco": .15, "aleatorio": .33},
        "R": {"nit": .08, "tag": .16, "station": .05, "maniaco": .50, "aleatorio": .33},
    },
    # --- §2.5 Estadísticas Beta (shrinkage) ---------------------------------------
    "beta": {
        "m": {"vpip": 0.30, "pfr": 0.12, "sigue_chica": 0.45, "sigue_grande": 0.35},  # provisional: se mide en Capa 2
        "s": {"vpip": 20, "pfr": 20, "sigue_chica": 20, "sigue_grande": 20},
        "x_chica_max": 0.6,       # apuesta chica: x <= 0,6; grande: x > 0,6
    },
    # --- §2.6 Olvido --------------------------------------------------------------
    "olvido": {"lambda": 0.98},
    # --- §2.7 Huella de los montos ------------------------------------------------
    "huella": {
        "cajas": [0.33, 0.4, 0.5, 0.6, 0.66, 0.75, 0.9, 1.0],
        "tolerancia": 0.03,
        "prior": {"propio": 0.5, "base": 0.1, "novato": 0.1, "espia": 0.1, "bandido": 0.1, "estadistico": 0.1},
        # columnas: .33 .4 .5 .6 .66 .75 .9 1.0 otro  (provisional: se mide con los bots)
        "tabla": {
            "base":        [.01, .40, .01, .01, .01, .52, .01, .01, .02],
            "novato":      [.20, .01, .44, .01, .01, .29, .01, .01, .02],
            "espia":       [.01, .01, .44, .24, .01, .01, .14, .12, .02],
            "bandido":     [.01, .01, .44, .01, .29, .01, .01, .20, .02],
            "estadistico": [.01, .01, .30, .08, .08, .08, .08, .08, .28],
            "propio":      [1 / 9] * 9,
        },
        "umbral": 0.9,
    },
    # --- §2.8 Rango preflop inicial -----------------------------------------------
    "preflop_rango": {"peso_top_pfr_si_paga": 0.3},
    # --- §3 Explotación -----------------------------------------------------------
    "explotacion": {"kappa": 1.0, "rho_max": 0.8, "n_min": 8, "tau": 0.7},
    # --- Solo pruebas -------------------------------------------------------------
    "debug": {"retardo_s": 0.0},   # pausa artificial por decisión (para poder matar a Bender a mitad de mesa)
    # --- Conexión (no viene del .tex) ---------------------------------------------
    "conexion": {
        "inicial_s": 60.0,        # cuánto reintentar la primera conexión
        "caida_s": 300.0,         # cuánto reintentar tras una caída (EOF a mitad de mano o error)
        "fin_s": 15.0,            # cuánto reintentar si la mesa cerró justo después de un mano_fin
        "espera_max_s": 2.0,      # tope del backoff entre intentos
        "timeout_saludo_s": 10.0,
        "keepalive_s": 60,
    },
}


def _mezclar(base, extra, ruta=""):
    """Merge profundo de `extra` sobre `base` (in situ). Falla si `extra` trae
    una clave que `base` no conoce."""
    for clave, valor in extra.items():
        camino = f"{ruta}.{clave}" if ruta else clave
        if clave not in base:
            raise KeyError(f"parámetro desconocido: {camino}")
        if isinstance(base[clave], dict) and isinstance(valor, dict):
            _mezclar(base[clave], valor, camino)
        else:
            base[clave] = valor


def cargar_params(ruta=None):
    """Devuelve una copia de PARAMS, con el JSON de `ruta` mezclado encima."""
    params = copy.deepcopy(PARAMS)
    if ruta:
        with open(ruta, encoding="utf-8") as archivo:
            _mezclar(params, json.load(archivo))
    return params
