# Paso 3: confirmación con darwin y novato (commit 66e1efd5; 1.5 h en esta corrida)

Campo: aleatorio:4,conservador:4,base:4,estadistico:4,bandido:4,espia:4,bender_v1:1,darwin:1,novato:1 + Bender; semillas 17000000+i (300 previstas). A = v1.3-limpers (K = 10 000); B = final (K = 6 000).

Absolutos:

| config | n | P(top 6) | P(sobrevivir) | puesto medio |
|---|---|---|---|---|
| A (v1.3-limpers) | 300 | 58.0 % | 45.0 % | 7.71 |
| B (final) | 300 | 62.7 % | 48.7 % | 7.12 |

| config | contra | n | Δ P(top 6) pts (IC 95 %) | Δ P(sobrevivir) pts (IC 95 %) | Δ P(quiebra) por campeonato pts | Δ tasa de quiebra por mesa pts (IC 95 %) | Δ puesto medio (IC 95 %) | Δ bb/100 (IC 95 %) |
|---|---|---|---|---|---|---|---|---|
| B (final) | A (v1.3-limpers) | 300 | +4.7 (-2.3 a +11.7) | +3.7 (-3.3 a +11.0) | -3.7 | -1.09 (-2.87 a +0.66) | -0.59 (-1.55 a +0.36) | +32 (-35 a +116) |

Δ P(top 6) = +4.7 (-2.3 a +11.7); Δ P(sobrevivir) = +3.7 (-3.3 a +11.0) con n = 300.

**B NO sale significativamente peor en P(top 6) ni en P(sobrevivir): se etiqueta v1.4-final.**