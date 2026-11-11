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
        # --- Reglas de solo valor (§1.11, activas por decisión del equipo tras el paso 3) ---
        "allin_profundo_solo_valor": True,    # en modo profundo, el all-in se descarta si e' < umbral_valor
        "solo_valor_sobre_apuesta": True,     # subir sobre una apuesta ajena solo si e' >= umbral_valor
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
    # CALIBRADO con los 6 bots de entrenamiento del kit (pruebas/calibrar.py sobre calib-1: 90 mesas, 100 manos):
    # base, estadistico, bandido, espia = TAG; conservador = station; aleatorio = aleatorio (+0,5 de suavizado).
    # El .tex trae .25/.25/.20/.15/.15 (provisional). Es el prior de la población de bots DEL KIT; los bots
    # que escriban los demás equipos pueden ser más variados.
    "prior_tipos": {"nit": .06, "tag": .53, "station": .18, "maniaco": .06, "aleatorio": .17},
    "piso_pi": 0.01,
    # P(accion | tipo) preflop por mano: F se retira, C entra pagando, R entra subiendo
    # CALIBRADO (pruebas/calibrar.py, calib-1): tag = promedio medido de base/estadistico/bandido/espia;
    # station = conservador; aleatorio = aleatorio. nit y maníaco no tienen bot en el kit: conservan la tabla del .tex.
    # La tabla del .tex (tag F.78/C.06/R.16, station F.45/C.50/R.05) hacía creer que base, estadistico y espia eran
    # "station" (los bots del kit pagan ~27 % de las manos, no 6 %) y Bender los trataba como rivales que pagan de todo.
    "preflop_verosimilitud": {
        "F": {"nit": .88, "tag": .65, "station": .06, "maniaco": .35, "aleatorio": .30},
        "C": {"nit": .04, "tag": .26, "station": .92, "maniaco": .15, "aleatorio": .14},
        "R": {"nit": .08, "tag": .09, "station": .02, "maniaco": .50, "aleatorio": .56},
    },
    # --- §2.5 Estadísticas Beta (shrinkage) ---------------------------------------
    "beta": {
        # m CALIBRADO (promedio de los 6 bots de entrenamiento, cada uno pesa igual; pruebas/calibrar.py, calib-1).
        # El .tex trae VPIP 0,30 provisional; PFR, sigue_chica y sigue_grande no tenían valor en el .tex.
        "m": {"vpip": 0.455, "pfr": 0.143, "sigue_chica": 0.692, "sigue_grande": 0.545},
        "s": {"vpip": 20, "pfr": 20, "sigue_chica": 20, "sigue_grande": 20},
        "x_chica_max": 0.6,       # apuesta chica: x <= 0,6; grande: x > 0,6
    },
    # --- §2.6 Olvido --------------------------------------------------------------
    "olvido": {"lambda": 0.98},
    # --- §2.7 Huella de los montos ------------------------------------------------
    "huella": {
        "cajas": [0.33, 0.4, 0.5, 0.6, 0.66, 0.75, 0.9, 1.0],
        "tolerancia": 0.03,
        # (los priors se normalizan al crear cada Rival)
        "prior": {"propio": 0.5, "base": 0.1, "novato": 0.1, "espia": 0.1, "bandido": 0.1, "estadistico": 0.1,
                  "aleatorio": 0.1},
        # columnas: .33 .4 .5 .6 .66 .75 .9 1.0 otro
        # CALIBRADO midiendo a cada bot en 90 mesas (1 803 apuestas de base, 914 de espia, 835 de estadistico, 633 de
        # bandido, 70 de aleatorio; pruebas/calibrar.py, calib-1), con suavizado de Laplace y piso 0,01.
        # "novato" queda con la fila del .tex (leída del código): es un rival de RESERVA, no se usa para calibrar.
        # "conservador" nunca apuesta: no tiene huella. Ojo: el .tex decía base .4=.40 y .75=.52; midiendo, .4=.77 y .75=.11.
        "tabla": {
            "base":        [.009, .766, .063, .009, .009, .114, .009, .009, .009],
            "novato":      [.20, .01, .44, .01, .01, .29, .01, .01, .02],
            "espia":       [.010, .010, .328, .465, .010, .010, .100, .059, .010],
            "bandido":     [.009, .009, .341, .009, .567, .009, .009, .035, .009],
            "estadistico": [.010, .010, .183, .114, .123, .154, .065, .026, .315],
            "aleatorio":   [.010, .033, .020, .033, .020, .010, .010, .020, .844],
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
    # --- Capa 1: opciones que el .tex no fija (extensiones propias) -----------------
    "capa1": {
        "activa": True,              # False = la "versión Capa 0" (solo check/fold), para comparar
        "rangos_poblacion": True,   # False = equity contra mano al azar (ablación: "Capa 1 sin rangos")
        "pi_defecto": {"tag": 1.0},  # tipo de rival sin datos: la fila "Promedio / TAG" de §2.2
        "estrecha_por_subida": 0.45,  # cada re-subida preflop reduce el top % del rival a este factor
        "min_pct_rango": 3.0,        # el rango de un re-subidor nunca baja de este top %
        "pct_bb_sin_posicion": 20.0,  # top % de quien sube desde una ciega grande (no está en §1.5)
        "semilla": None,             # None = azar del sistema; un entero hace reproducible la mezcla y el Monte Carlo
    },
    # --- Capa 2: memoria por ID de rival (rivales.py) ---------------------------------
    "rivales": {
        "activa": True,        # False = la Capa 1 sola (rival promedio para todos)
        "dir": None,           # carpeta de la memoria; None = bender/datos/rivales (ignorada por git)
        "persistir": True,     # guardar cada rival en disco al terminar cada mano
    },
    # --- Registro -----------------------------------------------------------------
    "registro": {"mensajes": True},  # False = no guarda cada mensaje crudo (corridas largas de evaluación)
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
