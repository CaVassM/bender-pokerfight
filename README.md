# Bender · bot de PokerFight (v1.4-final)

Bot de Texas Hold'em sin límite, 100 % probabilístico: toda decisión sale de probabilidades (equity simulada contra rangos, tablas de
apertura y Bayes) y una fórmula de utilidad; no usa LLM ni servicios externos. Responde en < 2 s (tope de 1,5 s por decisión; mediana ≈ 13 ms) y nunca envía una acción
fuera de `acciones_validas`.

## Cómo se corre

Requisitos: Python 3.11+ (probado con 3.14) y las dependencias de `requirements.txt` (`phevaluator`, `numpy`; `pytest` solo para los tests).

```
python -m venv bender/.venv
bender/.venv/Scripts/python -m pip install -r bender/requirements.txt     # en Linux/Mac: .venv/bin/python
bender/.venv/Scripts/python bender/main.py -addr localhost:9000 -token <token>
```

`-addr` es `host:puerto` de la mesa. El token va en `-token` o en la variable de entorno `BENDER_TOKEN`; nunca está en el código.
`-params archivo.json` sobreescribe cualquier número de `params.py`; `-log` y `-silencioso` controlan el registro JSONL por decisión.

**Comando del día del torneo y del servidor de pruebas** (desde la raíz del kit; el token sale de `BENDER_TOKEN`, la dirección es el único
argumento que cambia, y el log queda activado; el token nunca se escribe en el log):

```
# Windows (PowerShell)
$env:BENDER_TOKEN = "<token del equipo>"
bender\.venv\Scripts\python bender\main.py -addr <host>:<puerto> -log bender\logs\torneo.jsonl

# Linux / Mac
export BENDER_TOKEN="<token del equipo>"
bender/.venv/bin/python bender/main.py -addr <host>:<puerto> -log bender/logs/torneo.jsonl
```

Si falta el token termina con `bender: falta el token`; si la conexión se cae, reconecta solo con el mismo token. Un solo proceso por equipo.

## Cómo decide

- **Capa 0 · Robustez.** Conexión con reintentos y reconexión a mitad de mano; si faltan cartas o la estrategia lanza una excepción, juega una
  acción segura (pasar o retirarse) y deja la traza en el log. Cada acción se valida contra `acciones_validas` y hay un tope de tiempo.
- **Capa 1 · Cerebro.** Equity por simulación contra *rangos* (no contra manos al azar), menú de 5 acciones (retirarse, pasar/igualar, ½ pozo,
  pozo, all-in) y EV de cada una con la probabilidad de que el rival retire. Se elige por **utilidad con colchón**, u(S) = ln(S + K): como el
  objetivo es clasificar entre los 6 primeros y no maximizar fichas, evita jugarse el stack en monedas al aire. K = 6000 (§1.13).
- **Capa 2 · Lectura de rivales** (memoria por ID, aprende de todas las manos). Frecuencias con prior **Beta** y olvido (VPIP, PFR, cuánto
  sigue ante apuesta chica o grande); creencia **bayesiana** sobre el tipo de rival (nit, TAG, station, maníaco, aleatorio); **huella** de los
  montos para reconocer bots copiados del kit; y **explotación** acotada (ajusta rangos y umbrales según lo leído, con un tope de confianza).
- **Capa 3 · RL.** PPO se evaluó en el diseño y se descartó antes de implementarlo; se probaron un **bandido online** (UCB con descuento y Exp3,
  con respaldo jerárquico por rival → tipo → global, recompensa Δ ln(S + K)) y una **búsqueda offline** por *successive halving* sobre
  los parámetros. El bandido no
  ganó a los parámetros fijos (la recompensa por mano es demasiado ruidosa para distinguir brazos; ver `docs/bender_formulas_rl.tex`) y queda
  **apagado**. Lo que sí se usó: la búsqueda offline eligió **K = 6000**; el resto de parámetros se dejó en los valores de la hoja de fórmulas.

## Cómo se validó

Simulador de campeonato (`pruebas/campeonato.py`): 10 rondas de mesas de 5-6 jugadores, con 28 participantes y las fichas acumulándose entre
rondas, igual que el torneo (clasifican los 6 primeros). Cada comparación es **emparejada por semilla** (mismas cartas y mesas) con IC 95 %
por bootstrap. Campos: *entrenamiento* (bots del kit y copias de Bender), *desconocido* (copias de Bender con otros riesgos y bots de estrés,
para no sobreajustar a los bots del kit) y la confirmación con los bots de **reserva** (darwin y novato), que nunca se usaron para elegir.

| Prueba (300 campeonatos, semillas nuevas) | P(top 6) con K = 6000 | con K = 10 000 | Δ (IC 95 %) |
|---|---|---|---|
| Entrenamiento | 66,7 % | 60,3 % | +6,3 (−0,3 a +13,7) |
| Desconocido | 39,0 % | 39,7 % | −0,7 (−8,0 a +6,3) |
| Confirmación con darwin y novato | 62,7 % | 58,0 % | +4,7 (−2,3 a +11,7) |

K = 6000 no es significativamente peor en ningún campo y gana en promedio; con 300 semillas cada IC mide unos ±7 pts, así que la ganancia es
probable pero no demostrada. Se verifica con `bender/.venv/Scripts/python -m pytest bender` (240 tests). Detalle: `docs/bender_formulas.tex`
(fórmulas, fuente de verdad), `docs/DESVIACIONES.md` (dónde `params.py` difiere de la hoja) y `PENDIENTES.md`.
