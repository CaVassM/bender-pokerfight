# Última ronda «f1» (commit 4f912a23; 6.6 h en esta corrida)

## Campo DESCONOCIDO (bender_agresivo:7,bender_prudente:7,bender_v1:4,allin_siempre:2,iguala_siempre:2,sube_min_siempre:2,aleatorio:3 + Bender; semillas 14000000+i; 200 previstas)

Absolutos:

| config | n | P(top 6) | P(sobrevivir) | puesto medio |
|---|---|---|---|---|
| base | 200 | 32.0 % | 25.0 % | 10.51 |
| c05 | 200 | 38.0 % | 29.0 % | 8.96 |
| k6k | 200 | 38.0 % | 28.5 % | 9.36 |
| sin_contra | 200 | 42.0 % | 23.5 % | 10.14 |
| huella | 200 | 41.0 % | 28.5 % | 9.71 |

| config | contra | n | Δ P(top 6) pts (IC 95 %) | Δ P(sobrevivir) pts (IC 95 %) | Δ P(quiebra) por campeonato pts | Δ tasa de quiebra por mesa pts (IC 95 %) | Δ puesto medio (IC 95 %) | Δ bb/100 (IC 95 %) |
|---|---|---|---|---|---|---|---|---|
| c05 | base | 200 | +6.0 (-3.0 a +14.5) | +4.0 (-4.5 a +12.0) | -4.0 | -2.57 (-6.01 a +0.60) | -1.55 (-2.50 a -0.63) | +78 (+22 a +141) |
| k6k | base | 200 | +6.0 (-2.5 a +14.5) | +3.5 (-4.5 a +11.5) | -3.5 | -2.03 (-5.46 a +1.27) | -1.16 (-2.15 a -0.24) | +77 (+25 a +140) |
| sin_contra | base | 200 | +10.0 (+2.0 a +18.5) | -1.5 (-9.5 a +6.0) | +1.5 | -0.40 (-3.65 a +2.71) | -0.37 (-1.23 a +0.46) | -24 (-97 a +44) |
| huella | base | 200 | +9.0 (+0.5 a +17.5) | +3.5 (-5.0 a +12.0) | -3.5 | -1.73 (-5.27 a +1.72) | -0.80 (-1.73 a +0.14) | +9 (-66 a +79) |

| c05 | k6k | 200 | +0.0 (-9.0 a +9.0) | +0.5 (-7.5 a +8.5) | -0.5 | -0.54 (-3.52 a +2.44) | -0.40 (-1.32 a +0.53) | +1 (-33 a +33) |

**Reconocimiento de la huella en el campo desconocido**

| config | tipo real | (mano, rival) | reconocido como bot del kit | desglose | clase |
|---|---|---|---|---|---|
| base | aleatorio | 1105 | 3.6 % | aleatorio 4 % | kit: bien reconocido 4 % |
| base | allin_siempre | 1400 | 0.0 % | — | NO kit: falso positivo |
| base | bender_agresivo | 12979 | 40.0 % | espia 40 %, novato 0 % | NO kit: falso positivo |
| base | bender_prudente | 18930 | 40.0 % | espia 40 %, novato 0 % | NO kit: falso positivo |
| base | bender_v1 | 6352 | 39.2 % | espia 39 %, novato 0 % | NO kit: falso positivo |
| base | iguala_siempre | 247 | 61.5 % | conservador 62 % | NO kit: falso positivo |
| base | sube_min_siempre | 229 | 67.2 % | aleatorio 67 % | NO kit: falso positivo |
| c05 | aleatorio | 1204 | 12.4 % | aleatorio 12 % | kit: bien reconocido 12 % |
| c05 | allin_siempre | 1813 | 0.0 % | — | NO kit: falso positivo |
| c05 | bender_agresivo | 13362 | 39.0 % | espia 39 %, novato 0 % | NO kit: falso positivo |
| c05 | bender_prudente | 22010 | 42.6 % | espia 42 %, novato 0 % | NO kit: falso positivo |
| c05 | bender_v1 | 7910 | 36.5 % | espia 36 %, novato 0 % | NO kit: falso positivo |
| c05 | iguala_siempre | 266 | 63.2 % | conservador 63 % | NO kit: falso positivo |
| c05 | sube_min_siempre | 272 | 75.4 % | aleatorio 75 % | NO kit: falso positivo |
| k6k | aleatorio | 1082 | 1.6 % | aleatorio 2 % | kit: bien reconocido 2 % |
| k6k | allin_siempre | 1381 | 0.0 % | — | NO kit: falso positivo |
| k6k | bender_agresivo | 12872 | 38.4 % | espia 38 %, novato 0 % | NO kit: falso positivo |
| k6k | bender_prudente | 22624 | 44.9 % | espia 45 %, novato 0 % | NO kit: falso positivo |
| k6k | bender_v1 | 7954 | 42.1 % | espia 42 %, novato 0 % | NO kit: falso positivo |
| k6k | iguala_siempre | 250 | 61.6 % | conservador 62 % | NO kit: falso positivo |
| k6k | sube_min_siempre | 257 | 73.5 % | aleatorio 74 % | NO kit: falso positivo |
| sin_contra | aleatorio | 1310 | 8.4 % | aleatorio 8 % | kit: bien reconocido 8 % |
| sin_contra | allin_siempre | 1124 | 0.0 % | — | NO kit: falso positivo |
| sin_contra | bender_agresivo | 12946 | 39.4 % | espia 39 %, novato 0 % | NO kit: falso positivo |
| sin_contra | bender_prudente | 20211 | 42.7 % | espia 42 %, novato 0 % | NO kit: falso positivo |
| sin_contra | bender_v1 | 7345 | 39.4 % | espia 39 %, novato 1 % | NO kit: falso positivo |
| sin_contra | iguala_siempre | 187 | 50.8 % | conservador 51 % | NO kit: falso positivo |
| sin_contra | sube_min_siempre | 229 | 69.4 % | aleatorio 69 % | NO kit: falso positivo |
| huella | aleatorio | 1069 | 0.0 % | — | kit: bien reconocido 0 % |
| huella | allin_siempre | 1267 | 0.0 % | — | NO kit: falso positivo |
| huella | bender_agresivo | 12956 | 9.2 % | novato 8 %, estadistico 1 % | NO kit: falso positivo |
| huella | bender_prudente | 20882 | 12.7 % | novato 12 %, estadistico 0 % | NO kit: falso positivo |
| huella | bender_v1 | 6910 | 16.0 % | novato 15 %, estadistico 1 % | NO kit: falso positivo |
| huella | iguala_siempre | 232 | 51.3 % | conservador 51 % | NO kit: falso positivo |
| huella | sube_min_siempre | 289 | 54.7 % | aleatorio 55 % | NO kit: falso positivo |

| config | falsos positivos (rivales que NO son del kit reconocidos como bot del kit) |
|---|---|
| base | 38.7 % de los (mano, rival) |
| c05 | 39.1 % de los (mano, rival) |
| k6k | 41.5 % de los (mano, rival) |
| sin_contra | 40.2 % de los (mano, rival) |
| huella | 12.3 % de los (mano, rival) |

## Campo de ENTRENAMIENTO (aleatorio:4,conservador:4,base:4,estadistico:4,bandido:4,espia:4,bender_v1:3 + Bender; semillas 10000000+i, primeras 200; base y brazos de «conf1»)

Absolutos:

| config | n | P(top 6) | P(sobrevivir) | puesto medio |
|---|---|---|---|---|
| base (conf1) | 200 | 63.0 % | 46.0 % | 7.42 |
| c05 (conf1) | 200 | 69.5 % | 52.0 % | 6.49 |
| k6k (conf1) | 200 | 69.0 % | 53.5 % | 6.44 |
| sin_contra | 200 | 59.5 % | 36.0 % | 7.93 |
| huella | 200 | 59.5 % | 45.0 % | 7.35 |

| config | contra | n | Δ P(top 6) pts (IC 95 %) | Δ P(sobrevivir) pts (IC 95 %) | Δ P(quiebra) por campeonato pts | Δ tasa de quiebra por mesa pts (IC 95 %) | Δ puesto medio (IC 95 %) | Δ bb/100 (IC 95 %) |
|---|---|---|---|---|---|---|---|---|
| sin_contra | base (conf1) | 200 | -3.5 (-12.5 a +5.5) | -10.0 (-19.5 a -0.5) | +10.0 | +2.19 (-0.28 a +4.59) | +0.51 (-0.70 a +1.73) | -9 (-102 a +87) |
| huella | base (conf1) | 200 | -3.5 (-12.0 a +5.0) | -1.0 (-10.0 a +8.0) | +1.0 | +0.39 (-1.86 a +2.72) | -0.07 (-1.23 a +1.10) | +27 (-66 a +118) |

**Reconocimiento de la huella en el campo de entrenamiento (aquí los bots del kit SÍ están en la mesa)**

| config | tipo real | (mano, rival) | reconocido como bot del kit | desglose | clase |
|---|---|---|---|---|---|
| sin_contra | aleatorio | 2110 | 3.3 % | aleatorio 3 % | kit: bien reconocido 3 % |
| sin_contra | bandido | 15301 | 72.2 % | bandido 72 % | kit: bien reconocido 72 % |
| sin_contra | base | 7631 | 87.2 % | base 87 %, novato 0 %, conservador 0 % | kit: bien reconocido 87 % |
| sin_contra | bender_v1 | 12742 | 57.5 % | espia 57 %, novato 0 % | NO kit: falso positivo |
| sin_contra | conservador | 8479 | 83.3 % | conservador 83 % | kit: bien reconocido 83 % |
| sin_contra | espia | 8206 | 68.7 % | espia 69 % | kit: bien reconocido 69 % |
| sin_contra | estadistico | 5806 | 48.1 % | estadistico 47 %, aleatorio 1 %, espia 0 % | kit: bien reconocido 47 % |
| huella | aleatorio | 2188 | 0.0 % | — | kit: bien reconocido 0 % |
| huella | bandido | 15509 | 56.6 % | bandido 57 % | kit: bien reconocido 57 % |
| huella | base | 8306 | 73.1 % | base 73 % | kit: bien reconocido 73 % |
| huella | bender_v1 | 13292 | 12.8 % | novato 12 %, estadistico 1 % | NO kit: falso positivo |
| huella | conservador | 7802 | 80.4 % | conservador 80 % | kit: bien reconocido 80 % |
| huella | espia | 8382 | 57.6 % | espia 58 % | kit: bien reconocido 58 % |
| huella | estadistico | 5404 | 38.5 % | estadistico 39 % | kit: bien reconocido 39 % |


## Regla de elección (más simple que (i) no pierde en entrenamiento y (ii) gana o empata en el desconocido)

| config | (i) entrenamiento: Δ P(top 6) | (ii) desconocido: Δ P(top 6) |
|---|---|---|
| k6k | +6.0 (-2.0 a +14.0) → empata | +6.0 (-2.5 a +14.5) → empata |
| sin_contra | -3.5 (-12.5 a +5.5) → empata | +10.0 (+2.0 a +18.5) → gana |
| huella | -3.5 (-12.0 a +5.0) → empata | +9.0 (+0.5 a +17.5) → gana |
| c05 | +6.5 (-3.0 a +15.5) → empata | +6.0 (-3.0 a +14.5) → empata |