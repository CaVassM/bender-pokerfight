# Paso 2: bandido online «b1» (commit 8604a0df; 4.9 h en esta corrida)

## Campo de ENTRENAMIENTO (aleatorio:4,conservador:4,base:4,estadistico:4,bandido:4,espia:4,bender_v1:3 + Bender; semillas 10000000+i; brazos fijos de «conf1»)

Absolutos:

| config | n | P(top 6) | P(sobrevivir) | puesto medio |
|---|---|---|---|---|
| base (fijo) | 450 | 66.4 % | 48.0 % | 6.86 |
| c05 (fijo) | 450 | 66.4 % | 48.7 % | 6.81 |
| c24 (fijo) | 450 | 65.3 % | 46.4 % | 6.67 |
| k6k (fijo) | 450 | 67.1 % | 50.7 % | 6.57 |
| ucb (bandido) | 450 | 62.0 % | 46.4 % | 7.31 |
| exp3 (bandido) | 450 | 62.9 % | 46.2 % | 7.20 |

| selector | contra | n | Δ P(top 6) pts (IC 95 %) | Δ P(sobrevivir) pts (IC 95 %) | Δ P(quiebra) por campeonato pts | Δ tasa de quiebra por mesa pts (IC 95 %) | Δ puesto medio (IC 95 %) | Δ bb/100 (IC 95 %) |
|---|---|---|---|---|---|---|---|---|
| ucb | base (fijo) | 450 | -4.4 (-10.0 a +1.1) | -1.6 (-7.8 a +4.9) | +1.6 | +0.51 (-0.95 a +1.99) | +0.46 (-0.28 a +1.20) | +5 (-37 a +52) |
| ucb | c05 (fijo) | 450 | -4.4 (-10.2 a +1.3) | -2.2 (-8.4 a +4.0) | +2.2 | +0.89 (-0.49 a +2.34) | +0.50 (-0.30 a +1.31) | -59 (-147 a +14) |
| ucb | c24 (fijo) | 450 | -3.3 (-9.3 a +2.4) | +0.0 (-5.8 a +5.8) | -0.0 | +0.27 (-1.17 a +1.72) | +0.64 (-0.16 a +1.45) | -95 (-195 a -12) |
| exp3 | base (fijo) | 450 | -3.6 (-9.3 a +2.0) | -1.8 (-8.0 a +4.4) | +1.8 | +0.47 (-0.98 a +1.91) | +0.35 (-0.41 a +1.10) | +12 (-31 a +61) |
| exp3 | c05 (fijo) | 450 | -3.6 (-9.3 a +2.0) | -2.4 (-8.4 a +3.6) | +2.4 | +0.84 (-0.47 a +2.21) | +0.39 (-0.39 a +1.17) | -52 (-141 a +20) |
| exp3 | c24 (fijo) | 450 | -2.4 (-8.2 a +3.3) | -0.2 (-6.7 a +6.0) | +0.2 | +0.22 (-1.23 a +1.66) | +0.53 (-0.22 a +1.34) | -88 (-190 a -6) |

### Diagnóstico del bandido (entrenamiento)

- **ucb** (135582 manos con elección): uso base 33.8 %, c05 33.5 %, c24 32.7 %; explorando 50.0 % de las manos.
  - recompensa media por brazo jugado: base: z̄ +0.083 (±0.007), +2.28 bb/mano, 44860 manos; c05: z̄ +0.074 (±0.007), +1.83 bb/mano, 44466 manos; c24: z̄ +0.065 (±0.007), +1.95 bb/mano, 43394 manos
  - lo que Bender cree de cada rival (por tipo real): aleatorio: tipo:aleatorio 78 %, tipo:tag 9 %, bot:aleatorio 8 %; bandido: bot:bandido 74 %, tipo:tag 21 %, tipo:nit 4 %; base: bot:base 87 %, tipo:tag 12 %, tipo:station 1 %; bender_v1: bot:espia 56 %, tipo:tag 19 %, tipo:nit 12 %; conservador: bot:conservador 80 %, tipo:station 11 %, tipo:tag 9 %; espia: bot:espia 69 %, tipo:tag 28 %, tipo:nit 1 %; estadistico: tipo:tag 54 %, bot:estadistico 40 %, tipo:nit 4 %
- **exp3** (137088 manos con elección): uso base 48.0 %, c05 38.2 %, c24 13.7 %; explorando 49.8 % de las manos.
  - recompensa media por brazo jugado: base: z̄ +0.073 (±0.005), +2.22 bb/mano, 64098 manos; c05: z̄ +0.068 (±0.006), +1.77 bb/mano, 51424 manos; c24: z̄ +0.093 (±0.012), +1.80 bb/mano, 18677 manos
  - lo que Bender cree de cada rival (por tipo real): aleatorio: tipo:aleatorio 81 %, tipo:tag 10 %, bot:aleatorio 5 %; bandido: bot:bandido 74 %, tipo:tag 21 %, tipo:nit 4 %; base: bot:base 87 %, tipo:tag 12 %, tipo:station 0 %; bender_v1: bot:espia 58 %, tipo:tag 18 %, tipo:nit 12 %; conservador: bot:conservador 80 %, tipo:station 11 %, tipo:tag 9 %; espia: bot:espia 67 %, tipo:tag 30 %, tipo:nit 2 %; estadistico: tipo:tag 52 %, bot:estadistico 43 %, tipo:nit 4 %

## Campo DESCONOCIDO (bender_agresivo:7,bender_prudente:7,bender_v1:4,allin_siempre:2,iguala_siempre:2,sube_min_siempre:2,aleatorio:3 + Bender; semillas 11000000+i)

Absolutos:

| config | n | P(top 6) | P(sobrevivir) | puesto medio |
|---|---|---|---|---|
| base (fijo) | 100 | 31.0 % | 23.0 % | 10.77 |
| c05 (fijo) | 100 | 45.0 % | 37.0 % | 9.45 |
| c24 (fijo) | 100 | 35.0 % | 31.0 % | 10.24 |
| ucb (bandido) | 100 | 32.0 % | 21.0 % | 10.88 |
| exp3 (bandido) | 100 | 37.0 % | 25.0 % | 10.20 |

| selector | contra | n | Δ P(top 6) pts (IC 95 %) | Δ P(sobrevivir) pts (IC 95 %) | Δ P(quiebra) por campeonato pts | Δ tasa de quiebra por mesa pts (IC 95 %) | Δ puesto medio (IC 95 %) | Δ bb/100 (IC 95 %) |
|---|---|---|---|---|---|---|---|---|
| ucb | base (fijo) | 100 | +1.0 (-10.0 a +12.0) | -2.0 (-12.0 a +8.0) | +2.0 | +0.88 (-4.66 a +6.51) | +0.11 (-1.17 a +1.31) | -4 (-56 a +52) |
| ucb | c05 (fijo) | 100 | -13.0 (-23.0 a -3.0) | -16.0 (-25.0 a -6.0) | +16.0 | +7.00 (+3.00 a +11.47) | +1.43 (+0.12 a +2.80) | -52 (-135 a +31) |
| ucb | c24 (fijo) | 100 | -3.0 (-14.0 a +9.0) | -10.0 (-22.0 a +2.0) | +10.0 | +4.67 (-0.64 a +10.45) | +0.64 (-0.62 a +1.94) | +1 (-89 a +120) |
| exp3 | base (fijo) | 100 | +6.0 (-6.0 a +19.0) | +2.0 (-9.0 a +13.0) | -2.0 | -1.93 (-7.78 a +3.78) | -0.57 (-1.92 a +0.85) | -20 (-121 a +66) |
| exp3 | c05 (fijo) | 100 | -8.0 (-21.0 a +4.0) | -12.0 (-24.0 a +0.0) | +12.0 | +4.19 (-0.06 a +8.74) | +0.75 (-0.73 a +2.24) | -69 (-188 a +39) |
| exp3 | c24 (fijo) | 100 | +2.0 (-10.0 a +14.0) | -6.0 (-18.0 a +5.0) | +6.0 | +1.86 (-3.06 a +6.87) | -0.04 (-1.23 a +1.17) | -15 (-80 a +56) |
| c05 (fijo) | base (fijo) | 100 | +14.0 (+2.0 a +26.0) | +14.0 (+2.0 a +26.0) | -14.0 | -6.12 (-11.63 a -1.10) | -1.32 (-2.76 a +0.08) | +49 (-41 a +135) |
| c24 (fijo) | base (fijo) | 100 | +4.0 (-8.0 a +17.0) | +8.0 (-3.0 a +19.0) | -8.0 | -3.79 (-9.20 a +1.48) | -0.53 (-1.89 a +0.87) | -5 (-119 a +84) |

### Diagnóstico del bandido (desconocido)

- **ucb** (19263 manos con elección): uso base 35.9 %, c05 30.6 %, c24 33.5 %; explorando 75.9 % de las manos.
  - recompensa media por brazo jugado: base: z̄ +0.037 (±0.020), +0.71 bb/mano, 6772 manos; c05: z̄ +0.019 (±0.018), +0.57 bb/mano, 5762 manos; c24: z̄ +0.001 (±0.019), +0.16 bb/mano, 6302 manos
  - lo que Bender cree de cada rival (por tipo real): aleatorio: tipo:aleatorio 78 %, tipo:tag 10 %, bot:aleatorio 6 %; allin_siempre: tipo:aleatorio 94 %, tipo:tag 6 %; bender_agresivo: tipo:tag 41 %, bot:espia 38 %, tipo:maniaco 12 %; bender_prudente: tipo:tag 43 %, bot:espia 41 %, tipo:nit 11 %; bender_v1: tipo:tag 43 %, bot:espia 41 %, tipo:nit 9 %; iguala_siempre: bot:conservador 52 %, tipo:station 26 %, tipo:tag 22 %; sube_min_siempre: bot:aleatorio 63 %, tipo:tag 20 %, tipo:aleatorio 13 %
- **exp3** (21897 manos con elección): uso base 51.2 %, c05 34.0 %, c24 14.8 %; explorando 76.6 % de las manos.
  - recompensa media por brazo jugado: base: z̄ +0.022 (±0.015), +0.78 bb/mano, 10866 manos; c05: z̄ +0.034 (±0.015), +0.69 bb/mano, 7333 manos; c24: z̄ +0.019 (±0.027), +0.51 bb/mano, 3220 manos
  - lo que Bender cree de cada rival (por tipo real): aleatorio: tipo:aleatorio 84 %, tipo:tag 11 %, tipo:maniaco 5 %; allin_siempre: tipo:aleatorio 95 %, tipo:tag 5 %; bender_agresivo: bot:espia 40 %, tipo:tag 37 %, tipo:maniaco 13 %; bender_prudente: tipo:tag 46 %, bot:espia 42 %, tipo:nit 9 %; bender_v1: tipo:tag 46 %, bot:espia 41 %, tipo:nit 5 %; iguala_siempre: bot:conservador 55 %, tipo:station 24 %, tipo:tag 21 %; sube_min_siempre: bot:aleatorio 39 %, tipo:tag 37 %, tipo:aleatorio 15 %