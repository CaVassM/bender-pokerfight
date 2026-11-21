# Prueba final «f2» (commit 8a25c288; 7.6 h en esta corrida)

A = v1.3-limpers · B = k6k (solo K = 6000) · C = k6k + huella corregida (P(bot) ≥ 0,97, ≥ 8 apuestas con z, apertura preflop a 3 bb)

## Campo DESCONOCIDO (bender_agresivo:7,bender_prudente:7,bender_v1:4,allin_siempre:2,iguala_siempre:2,sube_min_siempre:2,aleatorio:3 + Bender; semillas 16000000+i, 300 previstas)

Absolutos:

| config | n | P(top 6) | P(sobrevivir) | puesto medio |
|---|---|---|---|---|
| A (base) | 300 | 39.7 % | 30.0 % | 9.83 |
| B (k6k) | 300 | 39.0 % | 29.0 % | 9.48 |
| C (k6k_huella) | 300 | 40.3 % | 31.7 % | 9.57 |

| config | contra | n | Δ P(top 6) pts (IC 95 %) | Δ P(sobrevivir) pts (IC 95 %) | Δ P(quiebra) por campeonato pts | Δ tasa de quiebra por mesa pts (IC 95 %) | Δ puesto medio (IC 95 %) | Δ bb/100 (IC 95 %) |
|---|---|---|---|---|---|---|---|---|
| B (k6k) | A (base) | 300 | -0.7 (-8.0 a +6.3) | -1.0 (-7.7 a +5.7) | +1.0 | +0.10 (-2.33 a +2.64) | -0.35 (-1.09 a +0.45) | +63 (-2 a +151) |
| C (k6k_huella) | A (base) | 300 | +0.7 (-7.0 a +8.0) | +1.7 (-5.7 a +8.7) | -1.7 | -0.56 (-3.14 a +2.14) | -0.26 (-1.05 a +0.55) | +80 (-9 a +196) |
| C (k6k_huella) | B (k6k) | 300 | +1.3 (-6.3 a +9.0) | +2.7 (-4.7 a +9.7) | -2.7 | -0.66 (-3.26 a +1.95) | +0.09 (-0.72 a +0.87) | +17 (-45 a +102) |

**Reconocimiento de la huella, campo DESCONOCIDO**

| config | tipo real | (mano, rival) | reconocido como bot del kit | desglose | clase |
|---|---|---|---|---|---|
| base | aleatorio | 1351 | 1.0 % | aleatorio 1 % | kit: bien reconocido 1 % |
| base | allin_siempre | 1835 | 0.0 % | — | NO kit: falso positivo |
| base | bender_agresivo | 21522 | 40.1 % | espia 40 %, novato 0 % | NO kit: falso positivo |
| base | bender_prudente | 32140 | 43.4 % | espia 43 %, novato 0 % | NO kit: falso positivo |
| base | bender_v1 | 11735 | 41.9 % | espia 42 %, novato 0 % | NO kit: falso positivo |
| base | iguala_siempre | 428 | 58.4 % | conservador 58 % | NO kit: falso positivo |
| base | sube_min_siempre | 453 | 76.2 % | aleatorio 76 % | NO kit: falso positivo |
| k6k | aleatorio | 1570 | 1.8 % | aleatorio 2 % | kit: bien reconocido 2 % |
| k6k | allin_siempre | 1790 | 0.0 % | — | NO kit: falso positivo |
| k6k | bender_agresivo | 21581 | 38.4 % | espia 38 %, novato 0 % | NO kit: falso positivo |
| k6k | bender_prudente | 32443 | 42.7 % | espia 42 %, novato 0 % | NO kit: falso positivo |
| k6k | bender_v1 | 12675 | 39.0 % | espia 39 %, novato 0 % | NO kit: falso positivo |
| k6k | iguala_siempre | 473 | 61.5 % | conservador 62 % | NO kit: falso positivo |
| k6k | sube_min_siempre | 407 | 73.0 % | aleatorio 73 % | NO kit: falso positivo |
| k6k_huella | aleatorio | 1453 | 0.7 % | aleatorio 1 % | kit: bien reconocido 1 % |
| k6k_huella | allin_siempre | 1885 | 0.0 % | — | NO kit: falso positivo |
| k6k_huella | bender_agresivo | 21426 | 13.1 % | novato 11 %, estadistico 2 % | NO kit: falso positivo |
| k6k_huella | bender_prudente | 32942 | 14.1 % | novato 14 %, estadistico 0 % | NO kit: falso positivo |
| k6k_huella | bender_v1 | 12131 | 14.8 % | novato 14 %, estadistico 1 % | NO kit: falso positivo |
| k6k_huella | iguala_siempre | 432 | 54.6 % | conservador 55 % | NO kit: falso positivo |
| k6k_huella | sube_min_siempre | 381 | 47.5 % | aleatorio 48 % | NO kit: falso positivo |

| config | falsos positivos (rivales que NO son del kit reconocidos como bot del kit) |
|---|---|
| A (base) | 41.3 % de los (mano, rival) |
| B (k6k) | 39.9 % de los (mano, rival) |
| C (k6k_huella) | 14.0 % de los (mano, rival) |

## Campo ENTRENAMIENTO (aleatorio:4,conservador:4,base:4,estadistico:4,bandido:4,espia:4,bender_v1:3 + Bender; semillas 15000000+i, 300 previstas)

Absolutos:

| config | n | P(top 6) | P(sobrevivir) | puesto medio |
|---|---|---|---|---|
| A (base) | 300 | 60.3 % | 43.7 % | 7.83 |
| B (k6k) | 300 | 66.7 % | 48.7 % | 6.79 |
| C (k6k_huella) | 300 | 63.3 % | 39.3 % | 7.37 |

| config | contra | n | Δ P(top 6) pts (IC 95 %) | Δ P(sobrevivir) pts (IC 95 %) | Δ P(quiebra) por campeonato pts | Δ tasa de quiebra por mesa pts (IC 95 %) | Δ puesto medio (IC 95 %) | Δ bb/100 (IC 95 %) |
|---|---|---|---|---|---|---|---|---|
| B (k6k) | A (base) | 300 | +6.3 (-0.3 a +13.7) | +5.0 (-2.3 a +12.7) | -5.0 | -1.36 (-3.13 a +0.44) | -1.04 (-2.01 a -0.08) | +32 (-12 a +76) |
| C (k6k_huella) | A (base) | 300 | +3.0 (-3.7 a +10.0) | -4.3 (-12.0 a +3.7) | +4.3 | +0.62 (-1.33 a +2.53) | -0.46 (-1.52 a +0.53) | +12 (-34 a +61) |
| C (k6k_huella) | B (k6k) | 300 | -3.3 (-10.0 a +3.7) | -9.3 (-16.3 a -1.3) | +9.3 | +1.98 (+0.25 a +3.68) | +0.58 (-0.39 a +1.50) | -20 (-60 a +23) |

**Reconocimiento de la huella, campo ENTRENAMIENTO**

| config | tipo real | (mano, rival) | reconocido como bot del kit | desglose | clase |
|---|---|---|---|---|---|
| base | aleatorio | 3594 | 4.3 % | aleatorio 4 % | kit: bien reconocido 4 % |
| base | bandido | 23302 | 74.4 % | bandido 74 % | kit: bien reconocido 74 % |
| base | base | 11452 | 87.9 % | base 88 %, novato 0 % | kit: bien reconocido 88 % |
| base | bender_v1 | 20239 | 59.4 % | espia 59 %, novato 0 % | NO kit: falso positivo |
| base | conservador | 11965 | 82.6 % | conservador 83 % | kit: bien reconocido 83 % |
| base | espia | 12009 | 66.4 % | espia 66 % | kit: bien reconocido 66 % |
| base | estadistico | 8897 | 48.3 % | estadistico 47 %, aleatorio 1 %, espia 0 % | kit: bien reconocido 47 % |
| k6k | aleatorio | 3944 | 4.7 % | aleatorio 5 % | kit: bien reconocido 5 % |
| k6k | bandido | 25289 | 74.3 % | bandido 74 % | kit: bien reconocido 74 % |
| k6k | base | 12622 | 89.3 % | base 89 %, novato 0 % | kit: bien reconocido 89 % |
| k6k | bender_v1 | 22476 | 60.2 % | espia 60 %, novato 0 % | NO kit: falso positivo |
| k6k | conservador | 11557 | 82.4 % | conservador 82 % | kit: bien reconocido 82 % |
| k6k | espia | 13844 | 69.3 % | espia 69 %, conservador 0 % | kit: bien reconocido 69 % |
| k6k | estadistico | 8772 | 46.1 % | estadistico 45 %, aleatorio 1 %, espia 0 % | kit: bien reconocido 45 % |
| k6k_huella | aleatorio | 3831 | 0.5 % | aleatorio 1 % | kit: bien reconocido 1 % |
| k6k_huella | bandido | 24177 | 53.8 % | bandido 54 % | kit: bien reconocido 54 % |
| k6k_huella | base | 11837 | 71.1 % | base 71 % | kit: bien reconocido 71 % |
| k6k_huella | bender_v1 | 21223 | 15.5 % | novato 13 %, estadistico 2 % | NO kit: falso positivo |
| k6k_huella | conservador | 11364 | 80.1 % | conservador 80 % | kit: bien reconocido 80 % |
| k6k_huella | espia | 13909 | 58.3 % | espia 58 % | kit: bien reconocido 58 % |
| k6k_huella | estadistico | 8324 | 38.7 % | estadistico 38 %, espia 0 %, bandido 0 % | kit: bien reconocido 38 % |

| config | falsos positivos (rivales que NO son del kit reconocidos como bot del kit) |
|---|---|
| A (base) | 59.4 % de los (mano, rival) |
| B (k6k) | 60.2 % de los (mano, rival) |
| C (k6k_huella) | 15.5 % de los (mano, rival) |

## Regla de no inferioridad

| comparación | campo | Δ P(top 6) | Δ P(sobrevivir) |
|---|---|---|---|
| B vs A | desconocido | -0.7 (-8.0 a +6.3) | -1.0 (-7.7 a +5.7) |
| B vs A | entrenamiento | +6.3 (-0.3 a +13.7) | +5.0 (-2.3 a +12.7) |
| C vs A | desconocido | +0.7 (-7.0 a +8.0) | +1.7 (-5.7 a +8.7) |
| C vs A | entrenamiento | +3.0 (-3.7 a +10.0) | -4.3 (-12.0 a +3.7) |
| C vs B | desconocido | +1.3 (-6.3 a +9.0) | +2.7 (-4.7 a +9.7) |
| C vs B | entrenamiento | -3.3 (-10.0 a +3.7) | -9.3 (-16.3 a -1.3) |

- B: (1) promedio de los dos campos de Δ P(top 6) vs A = +2.8 pts → cumple; (2) ningún Δ P(sobrevivir) significativamente negativo → cumple
- C: (1) promedio de los dos campos de Δ P(top 6) vs A = +1.8 pts → cumple; (2) ningún Δ P(sobrevivir) significativamente negativo → cumple; (3) no significativamente peor que B → NO cumple

**Configuración recomendada por la regla: B (k6k).**