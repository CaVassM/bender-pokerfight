# Bender · un bot de póker que decide con probabilidades

**Bender** es un bot de Texas Hold'em *No-Limit* para el torneo PokerFight. Cada decisión sale de probabilidades: equity simulada contra el
*rango* estimado de cada rival, el valor esperado de cada jugada y una utilidad logarítmica que cuida el stack. No usa LLM ni servicios externos;
responde en milisegundos y nunca envía una acción fuera de las que la mesa permite.

Este repositorio tiene el bot (Python), su hoja de fórmulas, las herramientas con que se evaluó y la bitácora de las decisiones y de los
experimentos que **no** funcionaron.

> Versión de la entrega: `v1.4.2-entrega`. El código del bot es idéntico al de `v1.4.1-final`.

## Resultados destacados

| Prueba | Resultado |
|---|---|
| Servidor de pruebas, 18-nov (95 rondas, 4 447 manos) | **+163 bb/100**, IC 95 % +115 a +210; ganó 68 de 95 rondas |
| Servidor de pruebas, 21-nov (63 rondas, 2 838 manos) | **+146 bb/100**, IC 95 % +89 a +201; ganó 48 de 63 rondas |
| Velocidad y robustez en el servidor | 0 timeouts y 1 sola conexión en ambas sesiones; mediana de respuesta ≈ 25 ms (23–29 ms), p95 < 80 ms, máximo 140 ms |
| Simulador de campeonato (10 rondas, 28 participantes, 300 campeonatos con rivales de reserva) | **P(top 6) ≈ 63 %** (62,7 %); el azar daría 6/28 ≈ 21 % |
| Simulador de la final (mesa de 6 contra 5 finalistas fuertes, 400 finales) | **P(ganar) ≈ 28 %** (28,0 %, IC 95 % 23,8–32,6); el azar daría 16,7 % |

Cómo leer estas cifras con honestidad:

- El servidor de pruebas juega contra bots del kit (los dos días fueron conservador, base, estadístico, bandido, espía y, el 21-nov, también novato
  y aleatorio), **repone 10 000 fichas cada ronda y no elimina a nadie**. No es el formato del torneo; sirve para medir ritmo, robustez y ventaja
  contra rivales débiles. Aun así hubo quiebras de ronda: 9 de 95 el 18-nov y 9 de 63 el 21-nov.
- La métrica que importa para clasificar (P(top 6)) sale del simulador, que sí reproduce el formato (ver [Lo interesante](#lo-interesante)).
- El simulador de la final usa un tope de 400 manos; el ritmo medido en el servidor (≈ 0,5–0,6 s por mano) sugiere que una hora de final tendría
  muchas más manos que eso, así que esa cifra es una estimación, no una predicción.

## Lógica de creación

Bender se construyó en este orden, y cada paso dejó rastro en el repositorio:

1. **Primero, la hoja de fórmulas.** Antes de escribir código se redactó, en LaTeX, cada fórmula con su tabla de parámetros y un ejemplo numérico:
   [`docs/bender_formulas.pdf`](docs/bender_formulas.pdf) (Parte 1: modelo probabilístico, Capas 1 y 2) y
   [`docs/bender_formulas_rl.pdf`](docs/bender_formulas_rl.pdf) (la parte de aprendizaje por refuerzo). Los `.tex` que las generan están en la misma
   carpeta. Las hojas explican la matemática; los valores vigentes viven en [`params.py`](params.py) y [`docs/DESVIACIONES.md`](docs/DESVIACIONES.md) lista cada punto donde el código difiere de ellas y por qué.
2. **Implementación por pasos y por capas**, con pruebas en cada paso: Capa 0 (conexión, reconexión y acción segura), Capa 1 (el cerebro: equity, EV,
   utilidad), Capa 2 (lectura de rivales y explotación) y Capa 3 (experimentos de RL, apagados por defecto).
3. **Calibración** con los bots del kit: los números que la hoja traía como «provisionales» (VPIP, plantillas de apuesta por categoría de mano,
   huellas de tamaños) se midieron con partidas reales y quedaron en [`datos/`](datos/) y en [`params.py`](params.py).
4. **Validación con un simulador de campeonato** (ver abajo) y reglas de adopción fijadas *antes* de mirar los resultados: un cambio entra solo si
   el IC 95 % de la diferencia emparejada excluye el 0 a su favor, o (para el valor final de K) si no es peor.

La bitácora completa —pendientes, decisiones, resultados y errores— está en [`PENDIENTES.md`](PENDIENTES.md).

**Sobre el uso de IA.** Bender se desarrolló con asistencia de IA: buena parte del código, de los tests y de las herramientas de evaluación se
escribió con Claude (Anthropic). El equipo definió el diseño y las reglas de adopción y aprobó cada cambio de parámetros por defecto.

## Mecánica de juego

Cada vez que la mesa le pide una acción, Bender recorre estos pasos (el detalle y las fórmulas completas están en la hoja de fórmulas):

| # | Paso | Qué hace | Fórmula clave |
|---|---|---|---|
| 1 | **Estado y stack efectivo** | Lee el estado de la mesa y fija, al empezar la mano, las fichas que cada jugador tenía: son las que cuentan, no las que quedan detrás en medio de la mano. | S⁰ = saldo + apuesta_ronda (en `mano_inicio`) |
| 2 | **Modo de juego** | Según el stack efectivo en ciegas grandes: *push/fold* (≤ 15 bb), *intermedio* (≤ 25 bb) o *profundo* (el normal, con 100 bb). | umbrales 15 / 25 bb |
| 3 | **Rango del rival** | Parte del rango típico de la posición y lo reajusta con cada acción observada (regla de Bayes sobre las 1 326 combinaciones de cartas, con un piso para no descartar nada del todo). | w̃(h) ∝ w(h) · máx(P(a ∣ h), 0,02) |
| 4 | **Equity por Monte Carlo** | Simula el resto de la mano contra el *rango* (no contra manos al azar) con un evaluador en C. Para cuando la estimación ya es precisa o está claramente lejos de un umbral de decisión. | parar si N ≥ 2 000 y (σ ≤ 0,005 o ∣e − e_ref∣ ≥ 3σ) |
| 5 | **EV de cada acción** | Arma un menú de cinco jugadas (retirarse, pasar/igualar, ½ pozo, pozo, all-in) y calcula su valor esperado con la *fold equity* f: la probabilidad de que todos los rivales se retiren. | EV(apostar) = f·P + (1 − f)·[e′·(P + A + A′) − A] |
| 6 | **Utilidad logarítmica** | En vez de maximizar fichas, maximiza la utilidad esperada de lo que le queda: así no juega a cara o cruz con todo el stack (para el objetivo —clasificar entre los 6 mejores— quedar eliminado cuesta más de lo que una buena apuesta rinde). | u(S) = ln(S + K), K = 6 000 |
| 7 | **Explotación por rival** | Lleva memoria por alias: estadísticas con prior Beta y olvido (VPIP, PFR, cuánto sigue ante una apuesta), un posterior bayesiano sobre su *tipo* (nit, TAG, station, maníaco, aleatorio) y una **huella de tamaños de apuesta** que detecta si es un bot copiado del kit. Cuánto se desvía de su juego sólido depende de la confianza. | ρ = ρ_max · máx(0, 1 − κ·σ / ∣p̂ − m∣) |
| 8 | **Reloj adaptativo** | Reparte el tiempo de la mesa entre sus decisiones: responde siempre muy por debajo del plazo de 5 s. | T_max = máx(T_piso, mín(T_tope, η·T_rest / D_rest)) |

Detalles que ayudan a entenderlo:

- **Preflop.** Si nadie subió, Bender abre solo con el *top %* de su posición (UTG 14,3 %, HJ 18,9 %, CO 25,5 %, BTN 43,3 %, SB 33,0 %) a 2,5 bb, o se
  retira: nunca entra pagando la ciega. Con limpers decide con el mismo menú de EV (iso-raise, over-limp o retirarse).
- **Explotar no es agregar reglas.** Lo que cambia entre un rival y otro son los *números* que entran a las mismas fórmulas (su fold equity, su rango).
  ρ_max = 0,8 y κ = 1 en la hoja: con pocas manos Bender confía poco en la lectura y con más datos se acerca al máximo.
- **Todo queda explicado.** Cada decisión escribe en el log el estado, la equity con su N, la tabla de EV de cada opción y el motivo; con eso se
  pueden reconstruir y auditar las manos después.
- **Seguridad.** Si faltan cartas, si hay una excepción o si la acción no está entre las válidas, juega la acción segura (pasar o retirarse) y deja la
  traza. Reconecta solo con el mismo token si se cae el socket.

### Las matemáticas, con un ejemplo en cada paso

Notación: **P** = pozo, **C** = lo que cuesta igualar, **A** = lo que agrega Bender al apostar, **e** = equity (probabilidad de ganar la mano; un
empate cuenta como media victoria), **S** = fichas que le quedan a Bender.

**1. Equity por Monte Carlo.** Se reparten al azar las cartas que faltan y las del rival (sacadas de su rango) y se cuenta cuántas veces gana Bender:

$$e=\frac{\text{victorias}+\tfrac12\,\text{empates}}{N},\qquad \sigma_e=\sqrt{\frac{e\,(1-e)}{N}}$$

Con N = 2 500 simulaciones, incluso en el peor caso (e = 0,5) el error típico es de 1 punto. Por eso Bender simula al menos 2 000 veces y para
cuando σₑ ≤ 0,005 (medio punto) o cuando la equity ya está claramente lejos del umbral que cambiaría su decisión.

**2. Igualar una apuesta.** Bender gana P + C si gana y pierde C si pierde:

$$EV(\text{igualar})=e\,(P+C)-C\ \ \Longrightarrow\ \ \text{conviene si}\ \ e>\frac{C}{P+C}$$

*Ejemplo:* con P = 600 y C = 300 necesita más de 300/900 = 33,3 % de equity.

**3. Apostar o subir: la fold equity.** Si Bender apuesta A, con probabilidad **f** todos se retiran y se lleva el pozo; si no, juega con la equity **e′**
que tiene contra los rivales que *pagan* (que no es la misma que contra todo su rango):

$$EV(\text{apostar})=f\,P+(1-f)\,\big[\,e'\,(P+A+A')-A\,\big],\qquad f=\prod_i\,(1-c_i)$$

donde A′ es lo que agrega el rival que paga y cᵢ la probabilidad de que el rival *i* siga en la mano.
*Ejemplo:* P = 600, A = A′ = 300, f = 0,49, e′ = 0,35 → 0,49·600 + 0,51·(0,35·1 200 − 300) ≈ **+355 fichas**. Un farol puro (e′ = 0) no pierde fichas
solo si f > A/(P + A): hace falta que se retiren el 33 % de las veces con A = P/2 y el 50 % con A = P.

**4. El rango del rival cambia con cada acción (Bayes).** Cada combinación *h* de cartas del rival tiene un peso. Cuando él actúa, ese peso se multiplica por
la probabilidad de que alguien con esa mano haga esa acción (el piso de 0,02 evita descartar una mano por completo):

$$w'(h)\ \propto\ w(h)\cdot\max\big(P(a\mid h),\ 0{,}02\big)$$

*Ejemplo:* en un flop J-7-2 quedan 259 combinaciones (43 fuertes, 45 medias, 171 «aire»). Si el rival paga, sus pesos pasan a 43·0,55, 45·0,60 y 171·0,07, y
el «aire» baja del 66 % al 19 % de su rango.

**5. Utilidad logarítmica: no jugarse todo a cara o cruz.** Para clasificar entre los 6 mejores, quedar eliminado cuesta mucho más de lo que una buena apuesta
rinde. Bender elige la acción con mayor utilidad esperada, con una función cóncava de las fichas que le quedan:

$$u(S)=\ln(S+K),\qquad K=6\,000\ \ (\text{el «colchón»})$$

*Ejemplo:* meter todo un stack de S = 10 000 a «doble o nada» solo es aceptable si la equity cumple

$$e\ \ge\ \frac{\ln\frac{S+K}{K}}{\ln\frac{2S+K}{K}}$$

| K | 5 000 | 6 000 | 10 000 | 40 000 | → ∞ |
|---|---|---|---|---|---|
| equity mínima | 68,3 % | 66,9 % | 63,1 % | 55,0 % | 50 % (maximizar fichas) |

(K = 6 000 es el valor final; su fila sale de la misma fórmula.) Cuanto más chico el colchón, más prudente.

**6. Cuánto explotar a cada rival.** Bender mide estadísticas de cada rival (por ejemplo su VPIP, el % de manos en que entra al bote) con un prior que
las acerca a lo normal al principio. Se desvía de su juego sólido solo en la medida en que la desviación del rival es *real* y no ruido:

$$\rho=\rho_{\max}\cdot\max\!\Big(0,\ 1-\kappa\,\frac{\sigma}{\lvert\hat p-m\rvert}\Big),\qquad \theta=(1-\rho)\,\theta_{\text{base}}+\rho\,\hat\theta$$

con p̂ el valor estimado del rival, m el valor de la población, σ la incertidumbre del estimado, ρ_max = 0,8 y κ = 1.
*Ejemplo* (VPIP de la población m = 0,30): tras 10 manos p̂ = 0,433 y σ = 0,089 → ρ = 0,8·(1 − 0,089/0,133) ≈ **0,26**; tras 85 manos p̂ = 0,552 y
σ = 0,048 → ρ ≈ **0,65**. Con más datos explota más; con pocos, casi no se mueve.

**7. Reloj adaptativo.** Con 360 s para 50 manos y unas 2,5 decisiones de Bender por mano, cada decisión puede usar

$$T_{\max}=\max\!\Big(T_{\text{piso}},\ \min\!\big(T_{\text{tope}},\ \eta\,\tfrac{T_{\text{rest}}}{D_{\text{rest}}}\big)\Big)$$

*Ejemplo* al empezar una mesa: 0,5·360/125 = 1,44 s (con T_tope = 1,5 s y T_piso = 0,25 s). En la práctica casi nunca hace falta: la mediana real es de ≈ 25 ms.

## Lo interesante

### Un simulador de campeonato propio

El kit oficial solo trae round-robin y mesa única, así que se escribió [`herramientas/campeonato`](herramientas/campeonato/main.go) (Go) que **reproduce
el formato real de la clasificatoria** con el motor de la mesa del kit: 10 rondas, mesas de 5 (algunas de 6) sorteadas de nuevo en cada ronda, 50
manos, ciegas 50/100, fichas que se arrastran, eliminación a 0 y pasan los 6 con más fichas. [`pruebas/campeonato.py`](pruebas/campeonato.py) lo
lanza con cientos de campeonatos (≈ 10 s cada uno) y calcula P(top 6), P(sobrevivir), puesto medio y tasa de quiebra.

- **Semillas emparejadas:** dos versiones de Bender juegan las mismas cartas y el mismo sorteo de mesas, y se comparan por diferencia con un
  **bootstrap** para el IC 95 %. Con 300 campeonatos cada IC mide unos ±7 puntos, por eso varias mejoras quedan como «probables pero no demostradas».
- **Higiene de evaluación:** ninguna medición corre desde la carpeta que se edita; `pruebas/evaluar_fijo.py` la ejecuta desde un `git worktree` de un
  commit fijo y guarda el hash en el resultado. Es reproducible, y editar el código no contamina una tanda en curso.
- **Contra el sobreajuste:** los bots **de reserva** (darwin y novato) no se usaron nunca para elegir parámetros, solo para la confirmación final; y
  hay un campo «desconocido» con copias de Bender de otros estilos y bots de estrés (que siempre hacen all-in, igualan o suben el mínimo).
- **Un simulador de la final** (`pruebas/final_sim.py`): una mesa de 6 contra copias de Bender con otros estilos, novato, darwin y bandido, con 5
  configuraciones comparadas por semilla. Resultado: ninguna le gana a la configuración final en P(ganar).

### Experimentos de RL que no se adoptaron (resultado negativo, documentado)

| Experimento | Qué se probó | Resultado |
|---|---|---|
| *Successive halving* sobre los parámetros | 48 configuraciones (K, olvido, ρ_max, κ, tamaño y anchura de la apertura…) con presupuesto creciente: 12 → 36 → 108 → 216 campeonatos | Ninguna pasó la regla: la mejor, c05, +8,7 pts de P(top 6) (IC −2,0 a +19,3). Confirmación con 450 campeonatos nuevos (600 acumulados con la validación): +2,2 (−2,7 a +7,3). [`halving/h1`](pruebas/salidas/halving/h1/informe.md), [`conf1`](pruebas/salidas/halving/conf1/informe.md) |
| **Bandido online**: UCB con descuento y Exp3 | Elige entre tres «brazos» de parámetros en cada mano, con valor jerárquico rival → tipo → global (*shrinkage*) y recompensa Δ ln(S + K) | No superó a los parámetros fijos: P(top 6) 62,0 % (UCB) y 62,9 % (Exp3) frente a 66,4 % del brazo base. [`halving/b1-ent`](pruebas/salidas/halving/b1-ent/informe.md) |
| Bandido dentro de la **final** simulada | UCB entre K = 6 000, K = 20 000 y EV puro | P(ganar) 25,5 % frente a 28,0 % de la configuración fija. [`final/fin1`](pruebas/salidas/final/fin1/informe.md) |
| PPO / RL con estados | — | No se implementó: el equipo lo descartó para el torneo. |

El valor final **K = 6 000** se adoptó por la regla de *no inferioridad*, no por superioridad demostrada: frente a K = 10 000 dio +4,7 puntos de
P(top 6) (IC −2,3 a +11,7) en la confirmación con darwin y novato ([`halving/f3`](pruebas/salidas/halving/f3/informe.md)).

### Errores que encontró la validación

- **Bender se retiraba ante un all-in con ases.** El stack efectivo usaba las fichas que le *quedaban detrás* a los rivales: con un rival all-in,
  su saldo es 0, el modo pasaba a push/fold y la regla de compromiso descartaba el call. Contra un bot que hace all-in siempre, el resultado
  pasó de **−147 a +167 bb/100** al corregirlo (usar S⁰, las fichas al empezar la mano). Tag `v1.2-fix`.
- **El reloj se quedaba sin tiempo en la final.** Pasados 360 s en una mesa, `T_rest ≤ 0` daba `T_max = 0` y cada decisión se hacía con 64
  simulaciones (σ ≈ 0,061) en vez de ≥ 2 000 (σ ≈ 0,011). La final dura hasta una hora en una sola mesa, así que se agregó un piso de 0,25 s. Tag
  `v1.4.1-final`.
- **Falso reconocimiento de bots.** Bender confundía a sus propias copias con el bot `espía` por la huella de tamaños. Se midió el efecto y una
  corrección candidata no pasó la regla de adopción: quedó apagada y documentada.

### Historia por versiones (tags)

| Tag | Qué cambió | Medida |
|---|---|---|
| `v1-probabilistico` | Primera versión completa: Capas 1 y 2 | P(top 6) 49,3 % (campo de entrenamiento) |
| `v1.1-riesgo` | Utilidad logarítmica con colchón (K = 10 000) | 49,3 % → 69,7 % (entrenamiento); 49,0 % → 57,3 % con darwin y novato |
| `v1.2-fix` | Stack efectivo con S⁰ (el error de los ases) | all-in siempre: −147 → +167 bb/100 |
| `v1.3-limpers` | Preflop con limpers (iso-raise) | +2,3 pts de P(top 6), empate con tendencia a favor |
| `v1.4-final` | K = 6 000 | +4,7 pts frente a K = 10 000 (no inferior) |
| `v1.4.1-final` | Piso de 0,25 s en el reloj | misma decisión en mesas al día |
| `v1.4.2-entrega` | Hojas de fórmulas en PDF, README y scripts de demo | sin cambios en el código del bot |

La suite tiene **243 tests** (`pruebas/test_*.py`).

### Limitaciones conocidas

Medidas en el servidor de pruebas (ver [`PENDIENTES.md`](PENDIENTES.md)):

- **Fold equity optimista.** En 1 529 apuestas y subidas (21-nov) Bender supuso un 47 % de folds y observó un 35 %; en el flop de los faroles supone
  ≈ 60 % y observa ≈ 27 %. Los faroles en total siguen ganando fichas.
- **Botes preflop re-subidos contra rangos tight.** Dos de las quiebras del 18-nov fueron de este tipo (99 contra QQ y AKo contra AA): Bender
  creía tener ≈ 0,5–0,6 de equity y tenía mucho menos. Con pocos casos, es una hipótesis, no una conclusión.

## Cómo se corre

Requisitos: Python 3.11+ (probado con 3.14) y las dependencias de `requirements.txt` (`phevaluator`, `numpy`; `pytest` solo para los tests).

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt     # Linux/Mac: .venv/bin/python
```

El token **nunca** va en un archivo ni en el código: se pasa por la variable de entorno `BENDER_TOKEN` (o `-token`).

```powershell
# Windows (PowerShell)
$env:BENDER_TOKEN = "<token del equipo>"
.venv\Scripts\python main.py -addr <host>:<puerto> -params params_servidor.json
```

```bash
# Linux / Mac
export BENDER_TOKEN="<token del equipo>"
.venv/bin/python main.py -addr <host>:<puerto> -params params_servidor.json
```

- `-params archivo.json` sobreescribe cualquier número de `params.py` (aquí, `params_servidor.json` sube los reintentos de conexión a 6 h).
- `-log ruta.jsonl` elige dónde se guarda el registro de la sesión (por defecto, `logs/`, que está en `.gitignore`); `-silencioso` apaga el eco.
- El registro guarda cada mensaje crudo (≈ 30 KB por mano). Para sesiones largas se apaga con `{"registro": {"mensajes": false}}` en el JSON de `-params`.
- Si falta el token termina con `bender: falta el token`. Si la conexión se cae, reconecta solo con el mismo token. Un solo proceso por equipo.

**Tests:** `.venv/Scripts/python -m pytest` (≈ 30 s). El repo está pensado para vivir como carpeta `bender/` dentro del kit oficial del torneo;
los scripts de `pruebas/` asumen esa disposición. Fuera del kit pasan 242 de 243: falla `test_evaluador_coincide_con_el_de_la_mesa`, que compara
el evaluador de manos con el del kit en Go y necesita esa carpeta. Para el simulador de campeonato también hace falta el kit
(`go build -o bin/campeonato.exe ./bender/herramientas/campeonato` desde su raíz). Para correr el bot no hace falta nada de eso.

## Estructura

| Archivo / carpeta | Qué hay |
|---|---|
| `main.py`, `conexion.py`, `registro.py` | Arranque, conexión TCP con reconexión y registro JSONL (Capa 0) |
| `estado.py`, `cartas.py` | Interpretación de los mensajes, cuentas de apuestas, cartas y evaluador de manos (phevaluator) |
| `equity.py`, `rangos.py` | Equity por Monte Carlo y rangos de manos (combinaciones y bloqueadores) |
| `capa1.py`, `poblacion.py` | El cerebro: menú de acciones, EV, utilidad y modelo de población |
| `rivales.py`, `explotacion.py` | Memoria por rival, posterior de tipo, huella y explotación (Capa 2) |
| `bot.py`, `params.py` | Orquestación de una decisión y todos los parámetros con su explicación |
| `bandido.py`, `calibracion_allin.py` | Experimentos de la Capa 3 y calibración opcional (apagados por defecto) |
| `datos/` | Calibraciones medidas con los bots del kit |
| `docs/` | Hojas de fórmulas (PDF y `.tex`) y [`DESVIACIONES.md`](docs/DESVIACIONES.md) |
| `herramientas/campeonato/` | Simulador del formato de la clasificatoria (Go) |
| `pruebas/` | Tests, scripts de evaluación y los informes de los experimentos (`pruebas/salidas/…/informe.md`) |

## Créditos y dependencias

| Componente | Uso | Licencia |
|---|---|---|
| [phevaluator](https://github.com/HenryRLee/PokerHandEvaluator) 0.6.0 | Evaluador de manos de póker en C | Apache License 2.0 |
| [numpy](https://numpy.org) 2.5.4 | Cálculo numérico | BSD de 3 cláusulas |
| [pytest](https://pytest.org) 9.2.0 | Solo para los tests | MIT |

- **Kit oficial del torneo** (organización de PokerFight). La aritmética de apuestas de `estado.py` (`apostar` y `apostar_pozo`) es un **port** de
  `Turno.Apostar` y `ApostarPozo` del SDK de Go del kit (`pkg/botsdk/botsdk.go`), porque es la cuenta que la mesa acepta.
- `herramientas/campeonato` **usa código del kit**: importa los paquetes `internal/mesa` e `internal/crupier` para jugar cada mesa con el motor
  real, y se compila dentro de la carpeta del kit.
- Los bots del kit (`base`, `espia`, `estadistico`, `bandido`, `conservador`, `aleatorio`, `novato`, `darwin`) se usan solo como rivales de prueba y
  no están incluidos aquí. `datos/` contiene calibraciones medidas jugando contra ellos.
- Desarrollado con asistencia de Claude (Anthropic), como se explica arriba.
