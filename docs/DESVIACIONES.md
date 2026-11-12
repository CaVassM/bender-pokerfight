# Lo que el código hace y el .tex no dice (o dice distinto)

Fuente de verdad: `bender_formulas.tex`. Esta lista es solo lo que el código decide y el .tex NO recoge. Ya
están en el .tex (y por eso no aparecen aquí): e'(x) por tamaño y ordenado por fuerza contra mano al azar,
reglas de solo valor, ×0,45 por re-subida, prior de tipos, m, tabla preflop F/C/R (incluida la columna
Aleatorio .30/.14/.56), huella calibrada, plantilla TAG calibrada (fuerte .14/.51/.34 …), la regla "las
plantillas genéricas no se cambian: un bot concreto tiene la suya", el filtro `filtros_tipo` apagado, y la
contraestrategia por bot (plantilla medida; Chen para `base`; `conservador` por comportamiento).

## Capa 1 y modelo de población

| # | Dónde | Qué hace el código | Por qué |
|---|---|---|---|
| 1 | §1.2 reloj | Siempre corre un bloque mínimo de 64 simulaciones, aunque T_max sea 0. Si los rangos no pueden convivir (cartas muertas) devuelve `imposible` y se cae a manos al azar. | Con T_max=0 no habría estimación; sin tope de intentos, un bucle infinito. |
| 2 | §1.7 / §3.3 c_i | `c_i` sale del **rango** del rival (postflop: plantilla §2.1 escalada a x; preflop: parte del rango dentro del umbral de fuerza de c_pob(x)). Solo sin rango se usa c(x) de §1.7. | §3.3 dice que θ_base de c_i es el c del rango. Con c(x) siempre, Bender re-subía hasta all-in con basura. |
| 3 | §1.9 multiway | Con varios rivales, pagan los `n = max(1, round(Σ c_i))` de mayor c_i y e' se calcula contra sus rangos de pago. | El .tex fija A' pero no cómo sale e' en multiway. |
| 4 | §1.9 A | Si el rival con más fichas no puede cubrir todo, la parte sobrante vuelve a Bender. | docs/reglas.md. |
| 5 | §1.9 fuerza postflop | Equity contra mano al azar: exacta en el river (monótona en el rank); en flop y turn, 96 repartos al azar COMPARTIDOS por board (cada combo usa los que no chocan con sus cartas; mismo estimador, 1 evaluación por reparto). Semilla fija por board. | El .tex pide "equity contra una mano al azar" sin decir cómo calcularla. |
| 6 | §1.6 call corto | Si el saldo no alcanza para igualar, EV usa lo que se puede cubrir. | docs/reglas.md. |
| 7 | §1.5 BB con opción | Si nadie subió y Bender es BB (C=0), decide con el menú EV (pasar o subir). | El .tex solo define apertura para quien tiene que pagar algo. |
| 8 | §1.5 apertura con limpers | Abre siempre a 2,5 bb (no suma una ciega por limper). | Literal del .tex. |
| 9 | §2.8 rangos de rivales | Quien solo paga: w=1 en VPIP sin PFR y 0,3 en el top del PFR; quien no actuó: mano al azar. Parámetros propios: `min_pct_rango`=3 %, `pct_bb_sin_posicion`=20 %. | El .tex deja esos números sin fijar. |
| 10 | ranking de 169 clases | Equity contra mano al azar con 4 M de simulaciones por clase. Los bordes de top-% del .tex caen a 2-6 combos de un borde de clase. | Decenas de clases a menos de 0,05 puntos entre sí. |

## Capa 2 (memoria por ID) y explotación

| # | Dónde | Qué hace el código | Por qué |
|---|---|---|---|
| 11 | §2.3 / §2.5 olvido | λ se aplica en **cada observación** de cada estadística y de log π (no por mano). | El .tex dice "primero se olvida, luego se suma". |
| 12 | §2.3 tipo con cartas | El tipo se actualiza con la primera decisión preflop de cada mano y con cada acción postflop SOLO si el rival mostró cartas. | Sin cartas no hay categoría. |
| 13 | §2.7 huella | Bayes puro (sin olvido). Las apuestas all-in o recortadas por el stack no cuentan. | §2.7. |
| 14 | §2.5 "sigue ante apuesta" | La apuesta enfrentada es la última apuesta/subida de la calle (su z); un all-in enfrentado no se cuenta. | El .tex no dice cómo medir x de la apuesta enfrentada. |
| 15 | observación | `Observador` reconstruye pozo y apuesta de cada momento (las ciegas no están en el historial) y se resincroniza con cada estado. | Necesario para calcular z. |
| 16 | persistencia | Un JSON por rival en `bender/datos/rivales/` (ignorado por git), al terminar cada mano. | §2.3. |
| 17 | §3.4 conservador | Se reconoce por comportamiento con un posterior bayesiano (H1 conservador vs H0 otro): agresión postflop 0,001 vs 0,2 por oportunidad (el mínimo medido en los demás bots es 0,21; el del conservador, 0 de 8 959), VPIP 0,82 vs 0,40, PFR 0,01 vs 0,14; prior 0,1, umbral 0,9 y mínimo de 10 oportunidades. | Nunca apuesta: no tiene huella de montos. |
| 18 | §3.4 base | Rango preflop exacto de `base`: sube con Chen ≥ 9 y paga con 5 ≤ Chen < 9 (puntuación portada de `bots/base/main.go`). | Sale de su código. |
| 19 | §3.4 aleatorio | "No darle crédito a sus subidas" = sus subidas no estrechan su rango (solo con `filtros_tipo`). | Es lo que dice el .tex; se mide con el interruptor. |
| 20 | §3.3 θ | Se mezcla (a) el c_i postflop con "sigue chica/grande" según x y (b) el ancho del rango preflop (VPIP/PFR). El c preflop por umbral de fuerza no se mezcla (las estadísticas son postflop). | El .tex dice "c_i y ancho del rango preflop". |
| 21 | interruptores | `explotacion.activa / usar_stats / filtros_tipo / contra_bots / chen_base`. | Evaluar cada pieza por separado. |

## Riesgo de quiebra (§1.13) y calibración de los all-in

| # | Dónde | Qué hace el código | Por qué |
|---|---|---|---|
| 22 | §1.13 utilidad | La utilidad esperada `u` y el equivalente cierto `ce` de cada opción se calculan SIEMPRE y quedan en el registro (`tabla_ev`: ev, u, ce, junto a `info.utilidad`); mandan en la elección si `riesgo.utilidad` es True, que es el valor POR DEFECTO desde `v1.1-riesgo` (K = 10 000). Con el interruptor apagado (`variantes/riesgo/v1.json`) se decide igual que el tag `v1-probabilistico` (comprobado: 250 spots, 0 diferencias en acción y EV). | Poder comparar y analizar sin cambiar nada. |
| 23 | §1.13 apertura | La apertura preflop (§1.5: top-% de la posición a 2,5 bb, sin EV) no pasa por la utilidad; sí push/fold y todo el menú de EV. | La apertura no tiene árbol de EV en el .tex. |
| 24 | calibración all-in | Solo rige con `calibracion_allin.activa`, en modo profundo (stack efectivo > 25 bb) y para el all-in del menú (no para x=0,5 ni x=1). Un rival cuenta como "empujó" solo si su acción es `allin` (una `raise` por todo su stack no se detecta). | Los datos son a 100 bb y de all-in; el modelo de población ya cubre el resto. |
| 25 | calibración all-in | No hay grupo `station`: conservador queda como bot propio. Nit y maníaco no se tocan (no hay bots así). Los conteos viven en `bender/calibracion_allin.py`, que regenera `pruebas/calibrar_allin.py` (no se edita a mano). | Decisión del usuario sobre las plantillas genéricas (paso 5). |
| 26 | §1.4 stack efectivo (ARREGLO, `v1.2-fix`) | S_ef = min(S⁰_Bender, max_i S⁰_i)/bb con S⁰ = fichas AL EMPEZAR LA MANO (saldo + lo ya puesto, leído en `mano_inicio`), fijo durante la mano; S⁰ de todos los que recibieron cartas, aunque se hayan retirado o estén all-in. Si no se vio el inicio de la mano (reconexión) se estima con saldo + apuesta_ronda del estado actual. | La versión anterior usaba las fichas que quedan detrás: un rival all-in valía 0 bb, Bender entraba en push/fold ante cualquier all-in y se retiraba hasta con AA (HU contra `allin_siempre` −147 bb/100). Definición del usuario. |
| 27 | §1.11 compromiso | Solo en modo intermedio; igualar un all-in cuyo coste es todo el stack de Bender cuenta como la opción «all-in» y no se descarta (en intermedio sigue «all-in o retirarse»). Se compara con `techo` (fichas detrás + apuesta de la calle), no con S⁰: el .tex dice «stack total», ambiguo; afecta poco (intermedio ≈ 1,4 % de las decisiones). | Instrucción del usuario: la regla es solo del modo intermedio. |
| 28 | §1.11 multiway | Cuentan los rivales que PUEDEN RESPONDER (con fichas detrás y no all-in), no todos los que siguen en la mano. | Un rival all-in no se retira ni paga más: no cambia el riesgo de farolear contra varios. |
| 29 | §1.9 e' con rivales all-in | e' (equity si pagan la apuesta) incluye el rango entero de los rivales all-in que siguen en el bote, además del rango de pago de los respondedores; antes los ignoraba y e' salía alta. NO se modelan los botes laterales: el árbol EV/utilidad trata el pozo como uno solo (P + A + A') aunque un rival all-in corto solo dispute el principal. | Auditoría del saldo de los rivales (A', respondedores, f, multiway, S de la utilidad: sin fallos; botes laterales: aproximación, ver PENDIENTES). |
| 30 | §1.5 preflop con limpers (`apertura.limpers_menu`, ENCENDIDO por defecto desde `v1.3-limpers`; False = v1.2-fix) | Con limpers sin subida se decide con el menú de EV/utilidad (retirarse, igualar, iso-raise, all-in) en vez de la tabla de apertura. La ciega grande también usa el iso (antes el menú genérico con fracciones de bote). Los limpers son los rivales con un `call` preflop y sin subida previa. Rango de cada limper = «solo pagó» de §2.8 (ya existía); quien no actuó, al azar. | El .tex solo cubría «nadie entró». En los logs de campeonato Bender se enfrenta a limpers en ~24 % de sus manos. |
| 31 | §1.5 iso-raise: A' de TODOS los pagadores | Solo para el iso-raise, el bote al que le pagan suma lo que agrega cada pagador (los `n_pago` de la fórmula de e'), no solo el mayor. El resto de las apuestas (flop, turn, river, apuestas sobre apuestas) siguen con un solo A'. | e' ya es contra todos los pagadores: con A' de uno solo el bote se subestima y todo iso sale con EV negativo. HALLAZGO ABIERTO: el mismo sesgo afecta a las apuestas multiway postflop (se subestima su EV); no se tocó, decisión del usuario. |
| 32 | §1.5 iso-raise sin multiway ni solo-valor, con piso `iso_margen` | El iso-raise no pasa por la regla multiway (§1.11, e' < 0,5 con ≥ 3 respondedores) ni por «subir solo sobre una apuesta»; se descarta si e' < `iso_margen`/(n_pago + 1) (1,25 ⇒ su parte justa con 25 % de margen). | Con 4 en el bote ni AK llega a e' = 0,5. El piso reparte: AK, QQ, AJs, 88 y KQo suben; 55 y JTs igualan; 72o se retira (2 limpers). Es una regla propia, no del .tex. |
| 33 | §1.5 sin all-in en profundo con limpers (`limpers_allin_profundo`, False) | En modo profundo no se ofrece el all-in sobre limpers; en intermedio sí. | El modelo de población da fold equity enorme a un all-in de ~22× el bote (+1 546 de EV con AK, sobre 2 limpers) y desplazaba al iso-raise; la ciega grande ya iba all-in en ~10 % de sus decisiones con limpers. |
| 34 | §1.5 `apertura_vs_station` | Tamaño de apertura (y base del iso) cuando el rival que habla DESPUÉS de Bender y tiene mayor π_station tiene π_station ≥ `vs_station_pi` (0,7). «El que más paga» se interpreta como el de mayor π_station. Por defecto = `tamano_bb` (sin efecto). | Instrucción del usuario; entra en la búsqueda del paso 1 en [2,5, 4,0]. |

## Solo en `params.py` (el .tex no trae los números)

- `plantillas_bot` y `prob_apuesta_bot`: plantilla medida de cada bot de entrenamiento (aleatorio, conservador, base, estadistico, bandido, espia), con shrinkage s = 20 hacia la de su grupo. Las plantillas genéricas (station, nit, maníaco, aleatorio) son las del .tex y no se tocan.
- `PLANTILLAS_TEX`: las filas provisionales del .tex (prior del shrinkage y de los tests).
- `conductual.conservador`: parámetros del reconocimiento por comportamiento (nº 17).
- `darwin` y `novato` (reserva) no tienen plantilla propia; `novato` conserva la fila de huella del .tex.

## Rendimiento

Con la máquina quieta: mediana 13 ms y p95 46 ms por decisión (flop 35/58 ms, turn 29/49 ms, river 11/17 ms). Con 6 corridas en paralelo: mediana 23 ms y p95 58 ms.
