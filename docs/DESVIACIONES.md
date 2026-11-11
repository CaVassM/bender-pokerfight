# Lo que el código hace y el .tex no dice (o dice distinto)

Fuente de verdad: `bender_formulas.tex`. Esta lista es lo que se decidió al implementar; lo que el .tex ya
incorporó (e'(x) por tamaño y ordenado por fuerza contra mano al azar, reglas de solo valor, ×0,45 por
re-subida) **ya no es una desviación** y no aparece aquí.

## Capa 1 y modelo de población

| # | Dónde | Qué hace el código | Por qué |
|---|---|---|---|
| 1 | §1.2 reloj | Siempre corre un bloque mínimo de 64 simulaciones, aunque T_max sea 0. Si los rangos no pueden convivir (cartas muertas) devuelve `imposible` y se cae a manos al azar. | Con T_max=0 no habría estimación; sin tope de intentos, un bucle infinito. |
| 2 | §1.7 / §3.3 c_i | `c_i` sale del **rango** del rival (postflop: plantilla §2.1 escalada a x; preflop: parte del rango dentro del umbral de fuerza de c_pob(x)). Solo sin rango se usa c(x) de §1.7. | §3.3 dice que θ_base de c_i es el c del rango. Con c(x) siempre, Bender re-subía hasta all-in con basura (−510 000 fichas en 1 800 manos heads-up). |
| 3 | §1.9 multiway | Con varios rivales, pagan los `n = max(1, round(Σ c_i))` de mayor c_i y e' se calcula contra sus rangos de pago (cada uno, su fracción c_i más fuerte). | El .tex fija A' (rival con más fichas) pero no cómo sale e' en multiway. |
| 4 | §1.9 A | Si el rival con más fichas no puede cubrir todo, la parte sobrante vuelve a Bender (A_ef = min(A, fichas que el rival puede igualar)). | Fichas no igualadas no se pierden (docs/reglas.md). |
| 5 | §1.9 fuerza postflop | La fuerza de un combo en el board es su equity contra una mano al azar: exacta en el river (monótona en el rank), Monte Carlo de 64 simulaciones por combo en flop y turn (semilla fija por board). | El .tex pide "equity contra una mano al azar" sin decir cómo calcularla. Es lo que más cuesta en tiempo (ver DESVIACIONES de rendimiento abajo). |
| 6 | §1.6 call corto | Si el saldo no alcanza para igualar, EV usa lo que se puede cubrir; lo no cubierto vuelve a su dueño. | docs/reglas.md. |
| 7 | §1.5 BB con opción | Si nadie subió y Bender es BB (C=0), no abre por tabla: decide con el menú EV (pasar o subir). Sin limp para el resto. | El .tex solo define apertura para quien tiene que pagar algo. |
| 8 | §1.5 apertura con limpers | Abre siempre a 2,5 bb (no suma una ciega por limper). | Literal del .tex. |
| 9 | §2.8 rangos de rivales | Quien solo paga: w=1 en VPIP sin PFR y 0,3 en el top del PFR (VPIP=m, calibrado 0,455); quien no actuó: mano al azar. Sin ρ (paso 5), el rango de quien sube es el top % de su posición. Parámetros propios: `min_pct_rango`=3 %, `pct_bb_sin_posicion`=20 %. | El .tex deja esos números sin fijar. |
| 10 | §2.2 tipo sin Capa 2 | Rival sin memoria = fila "Promedio / TAG" pura (π={'tag':1}). Con Capa 2 (por defecto) parte del prior calibrado. | El ejemplo de §2.1 usa esa fila (c=0,37). |
| 11 | ranking de 169 clases | Equity contra mano al azar con 4 M de simulaciones por clase. Los bordes de top-% del .tex (14,3 / 18,9 / 25,5 / 43,3) caen a 2-6 combos de un borde de clase. | Decenas de clases a menos de 0,05 puntos entre sí: el orden exacto no se puede reproducir. |

## Capa 2 (memoria por ID)

| # | Dónde | Qué hace el código | Por qué |
|---|---|---|---|
| 12 | §2.3 / §2.5 olvido | λ se aplica en **cada observación** de cada estadística y de log π (no por mano). Con λ=1 se recupera Bayes puro (test del ejemplo "station 20 % → 50,6 %"). | El .tex dice "primero se olvida, luego se suma la observación nueva". |
| 13 | §2.3 tipo con cartas | El tipo se actualiza (a) con la primera decisión preflop de cada mano (F/C/R) y (b) con cada acción postflop SOLO si el rival mostró cartas en el showdown (así se conoce la categoría de su mano). | Sin cartas no hay categoría. |
| 14 | §2.7 huella | Bayes puro (sin olvido): un bot del kit no cambia de estilo. Las apuestas all-in o recortadas por el stack no cuentan. | Así lo dice §2.7; el olvido de §2.6 no se aplica a la huella. |
| 15 | §2.5 "sigue ante apuesta" | La apuesta enfrentada es la última apuesta/subida de la calle (su z); chica x ≤ 0,6, grande x > 0,6. Un all-in enfrentado no se cuenta (su z no está definido). | El .tex no dice cómo medir x de la apuesta enfrentada. |
| 16 | observación | `Observador` reconstruye pozo y apuesta de cada momento (las ciegas no están en el historial) y se resincroniza con el estado real en cada mensaje. | Necesario para calcular z. |
| 17 | persistencia | Un JSON por rival en `bender/datos/rivales/` (ignorado por git), escrito al terminar cada mano; una evaluación usa su propia carpeta. | §2.3: "guardado por ID del rival, en disco". |

## Calibración con los bots del kit (paso 4)

Ver `bender/datos/calibracion.json` y `pruebas/calibrar.py`. Se calibraron con los 6 rivales de ENTRENAMIENTO
(darwin y novato no entran) en 90 mesas de 5 de 100 manos:

| Parámetro | Antes (.tex, provisional) | Ahora | Nota |
|---|---|---|---|
| huella P(z\|bot) | tabla leída del código | medida (base .4=.77, .75=.11; espia .5=.33, .6=.47; bandido .5=.34, .66=.57; estadistico repartido, 32 % "otro"; aleatorio 84 % "otro") | `base` NO pone 0,75 pozo la mayoría de las veces: lo hace solo con trío o mejor. `novato` conserva la fila del .tex (reserva). `conservador` no apuesta: sin huella. |
| m (VPIP, PFR, sigue chica, sigue grande) | 0,30 / — / — / — | 0,455 / 0,143 / 0,692 / 0,545 | Promedio simple de los 6 bots; arrastrado hacia arriba por conservador (VPIP 0,82) y aleatorio (0,67). |
| prior de tipos | .25/.25/.20/.15/.15 | .06/.53/.18/.06/.17 (nit/tag/station/maníaco/aleatorio) | base, estadistico, bandido, espia = TAG; conservador = station; aleatorio = aleatorio. Es la población DE BOTS DEL KIT. |
| P(F/C/R \| tipo) preflop | tag .78/.06/.16, station .45/.50/.05 | tag .65/.26/.09, station .06/.92/.02, aleatorio .30/.14/.56 (nit y maníaco: del .tex) | Con la tabla del .tex Bender creía que base, estadistico y espia eran "station" (los bots del kit pagan ~27 % de las manos, no 6 %). |

## Rendimiento

El orden por fuerza de §1.9 (nº 5) subió el tiempo por decisión: mediana ~30 ms y p95 ~175 ms (antes 15 ms y 44 ms), con 6 corridas en paralelo.
