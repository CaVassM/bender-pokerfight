# Halving «h1» (commit 23d80d49; campo aleatorio:4,conservador:4,base:4,estadistico:4,bandido:4,espia:4,bender_v1:3 + candidato; 5.4 h en esta corrida)

## Ronda 1 (12 campeonatos acumulados): Δ contra la base, emparejado

| config | n | Δ puesto medio | Δ P(top 6) pts | Δ P(sobrevivir) pts | Δ bb/100 |
|---|---|---|---|---|---|
| c24 | 12 | -1.75 | +16.7 | +0.0 | -30 |
| c13 | 12 | -1.17 | +8.3 | +41.7 | +127 |
| c04 | 12 | -0.58 | +0.0 | +33.3 | +132 |
| c05 | 12 | -0.50 | +8.3 | +33.3 | +120 |
| c37 | 12 | -0.42 | +0.0 | -8.3 | -37 |
| c02 | 12 | -0.25 | +8.3 | +8.3 | +64 |
| c36 | 12 | -0.25 | +0.0 | +16.7 | +17 |
| c01 | 12 | -0.08 | +8.3 | +0.0 | +17 |
| c23 | 12 | +0.17 | -8.3 | +8.3 | +14 |
| c41 | 12 | +0.17 | -16.7 | +16.7 | +71 |
| c44 | 12 | +0.33 | +8.3 | +0.0 | -64 |
| c08 | 12 | +0.67 | +8.3 | +25.0 | -747 |
| c32 | 12 | +0.67 | +0.0 | +8.3 | +89 |
| c09 | 12 | +0.92 | +0.0 | +25.0 | +88 |
| c18 | 12 | +1.00 | +0.0 | +8.3 | -15 |
| c26 | 12 | +1.00 | -8.3 | +16.7 | -5 |
| c20 | 12 | +1.08 | -8.3 | +16.7 | +37 |
| c34 | 12 | +1.08 | -16.7 | -8.3 | -29 |
| c06 | 12 | +1.33 | -8.3 | +16.7 | +136 |
| c10 | 12 | +1.33 | +0.0 | +16.7 | -742 |

## Ronda 2 (36 campeonatos acumulados): Δ contra la base, emparejado

| config | n | Δ puesto medio | Δ P(top 6) pts | Δ P(sobrevivir) pts | Δ bb/100 |
|---|---|---|---|---|---|
| c05 | 36 | -1.14 | +8.3 | +30.6 | +188 |
| c24 | 36 | -1.06 | +8.3 | +13.9 | +12 |
| c26 | 36 | -0.83 | +0.0 | +16.7 | +61 |
| c44 | 36 | -0.72 | +2.8 | +11.1 | +151 |
| c09 | 36 | -0.33 | -5.6 | +13.9 | +117 |
| c23 | 36 | -0.33 | -5.6 | +13.9 | +144 |
| c02 | 36 | -0.06 | -2.8 | +8.3 | +102 |
| c41 | 36 | -0.03 | -8.3 | +8.3 | +131 |
| c13 | 36 | +0.00 | +0.0 | +22.2 | +95 |

## Ronda 3 (108 campeonatos acumulados): Δ contra la base, emparejado

| config | n | Δ puesto medio | Δ P(top 6) pts | Δ P(sobrevivir) pts | Δ bb/100 |
|---|---|---|---|---|---|
| c24 | 108 | -0.39 | +4.6 | +2.8 | -9 |
| c05 | 108 | +0.09 | +0.9 | +5.6 | +34 |
| c09 | 108 | +0.17 | +0.0 | +2.8 | +33 |
| c26 | 108 | +0.27 | -2.8 | -3.7 | -35 |
| c44 | 108 | +0.55 | -3.7 | -1.9 | -25 |

## Ronda 4 (216 campeonatos acumulados): Δ contra la base, emparejado

| config | n | Δ puesto medio | Δ P(top 6) pts | Δ P(sobrevivir) pts | Δ bb/100 |
|---|---|---|---|---|---|
| c24 | 216 | -0.49 | +5.6 | +0.9 | +41 |
| c05 | 216 | -0.20 | +1.4 | +2.8 | -14 |

## Validación con 150 campeonatos de semillas NUEVAS (emparejado contra la base)

| finalista | Δ P(top 6) pts (IC 95 %) | Δ P(sobrevivir) pts (IC 95 %) | Δ puesto medio (IC 95 %) | Δ bb/100 (IC 95 %) | ¿gana? |
|---|---|---|---|---|---|
| c05 | +8.7 (-2.0 a +19.3) | +3.3 (-8.0 a +14.7) | -1.36 (-2.92 a +0.30) | +116 (-54 a +347) | no |
| c24 | +5.3 (-5.3 a +15.3) | -0.7 (-12.0 a +10.7) | -0.95 (-2.42 a +0.59) | +73 (-101 a +303) | no |

**Ninguna finalista le gana a la base con IC 95 % que excluya el 0: no se cambian los valores por defecto.**

## Finalistas: parámetros

- c05: flags (allin_profundo_solo_valor, solo_valor_sobre_apuesta) = [True, True]; K=6.25e+03, olvido=0.00568, rho_max=0.604, kappa=1.56, s_prior=38.3, tamano_bb=2.28, escala_rangos=0.942, iso_por_limper=1.25, apertura_vs_station=3.08
- c24: flags (allin_profundo_solo_valor, solo_valor_sobre_apuesta) = [True, False]; K=5.2e+03, olvido=0.00596, rho_max=0.676, kappa=0.768, s_prior=35.6, tamano_bb=2.64, escala_rangos=1, iso_por_limper=1.34, apertura_vs_station=2.52

## Importancia de parámetros (indicio): regresión de Δ puesto medio de la ronda 1 (12 campeonatos × 48 configuraciones) sobre los parámetros en [-1, 1]

Coeficiente = cambio del puesto medio al pasar del mínimo al máximo del rango (÷ 2 por unidad); negativo = mejora. |t| > 2 sería «suficiente» con un solo contraste, pero aquí hay 11 y solo 48 puntos ruidosos: es un indicio.

| parámetro | coeficiente | error estándar | t |
|---|---|---|---|
| escala_rangos | +1.381 | 0.426 | +3.25 |
| allin_profundo_solo_valor | -0.666 | 0.218 | -3.05 |
| K | +1.102 | 0.424 | +2.60 |
| solo_valor_sobre_apuesta | -0.357 | 0.219 | -1.64 |
| apertura_vs_station | -0.474 | 0.410 | -1.16 |
| olvido | +0.269 | 0.408 | +0.66 |
| s_prior | +0.254 | 0.402 | +0.63 |
| iso_por_limper | -0.257 | 0.436 | -0.59 |
| tamano_bb | -0.228 | 0.435 | -0.53 |
| kappa | -0.198 | 0.388 | -0.51 |
| rho_max | +0.037 | 0.429 | +0.09 |