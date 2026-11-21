# Final simulada (commit a1c3ac6a): 400 finales emparejadas por configuración

Mesa de 6 (Bender + bender_agresivo, bender_v1, novato, darwin, bandido), 10 000 fichas, ciegas 50/100, hasta que quede uno o 400 manos (gana el de más fichas). Semillas 18000000+i. Azar puro: P(ganar) = 16,7 %. Finales descartadas (error del conductor en alguna configuración): 0.

| configuración | P(ganar) | IC 95 % | P(top 2) | P(top 3) | puesto medio (IC) | manos medias | acaba por tope |
|---|---|---|---|---|---|---|---|
| a · v1.4-final (K = 6000) | 28.0 % | 23.8-32.6 | 48.5 % | 66.2 % | 2.86 (±0.16) | 329 | 51 % |
| b · K = 20 000 | 28.0 % | 23.8-32.6 | 41.0 % | 53.2 % | 3.21 (±0.18) | 323 | 53 % |
| c · K = 40 000 | 26.5 % | 22.4-31.0 | 38.0 % | 50.8 % | 3.36 (±0.18) | 324 | 51 % |
| d · utilidad apagada (EV puro) | 20.8 % | 17.1-25.0 | 30.2 % | 44.8 % | 3.57 (±0.17) | 311 | 48 % |
| e · bandido UCB entre a, b y d | 25.5 % | 21.5-30.0 | 38.5 % | 52.0 % | 3.27 (±0.17) | 312 | 46 % |

Diferencias EMPAREJADAS contra (a), por semilla (IC 95 % por bootstrap; la última columna es el IC con corrección de Bonferroni para 4 comparaciones, 98,75 %):

| config | Δ P(ganar) | IC 95 % | IC 98,75 % | Δ P(top 2) | IC 95 % | Δ P(top 3) | IC 95 % | Δ puesto | IC 95 % |
|---|---|---|---|---|---|---|---|---|---|
| b · K = 20 000 | +0.0 pts | -5.5 a +5.5 | -6.8 a +7.2 | -7.5 pts | -13.5 a -1.5 | -13.0 pts | -18.5 a -7.5 | +0.36 | +0.17 a +0.55 |
| c · K = 40 000 | -1.5 pts | -7.5 a +4.2 | -9.2 a +5.8 | -10.5 pts | -16.8 a -4.5 | -15.5 pts | -21.2 a -9.8 | +0.50 | +0.31 a +0.70 |
| d · utilidad apagada (EV puro) | -7.2 pts | -13.2 a -1.2 | -14.8 a +0.5 | -18.2 pts | -24.5 a -12.0 | -21.5 pts | -27.0 a -15.8 | +0.71 | +0.51 a +0.91 |
| e · bandido UCB entre a, b y d | -2.5 pts | -8.5 a +3.2 | -10.0 a +5.0 | -10.0 pts | -15.8 a -4.0 | -14.2 pts | -19.5 a -8.8 | +0.41 | +0.22 a +0.59 |

**Ninguna configuración le gana a (a) en P(ganar) con el IC 95 % por encima de 0: Bender juega la final igual que la clasificatoria.**

Ganador de la mesa (config a, todas las semillas válidas):

bender: 28 %, bender_v1: 23 %, bender_agresivo: 20 %, novato: 13 %, bandido: 9 %, darwin: 7 %

Uso de brazos del bandido (e): a 29 %, b 38 %, d 33 %

Tiempo por final: media 41 s (mediana 38 s).