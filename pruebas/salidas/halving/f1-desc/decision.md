# Regla de elección de la versión final

| config | Δ P(top 6) entrenamiento (IC 95 %) | Δ P(top 6) desconocido (IC 95 %) | falsos positivos de la huella |
|---|---|---|---|
| base | — | — | 38.7 % |
| k6k | +0.7 (-5.1 a +6.2) | +6.0 (-2.5 a +14.5) | 41.5 % |
| c05 | +2.2 (-2.7 a +7.3) | +6.0 (-3.0 a +14.5) | 39.1 % |
| sin_contra | -3.5 (-12.5 a +5.5) | +10.0 (+2.0 a +18.5) | 40.2 % |
| huella | -3.5 (-12.0 a +5.0) | +9.0 (+0.5 a +17.5) | 12.3 % |

- huella (arreglo): no pierde en entrenamiento NO; en desconocido sí; falsos positivos 38.7 % → 12.3 % (bajan)
- sin_contra (arreglo): no pierde en entrenamiento NO; en desconocido sí; falsos positivos: no aplica (la huella no cambia)
- k6k (parámetros): gana en desconocido NO; no pierde en entrenamiento sí
- c05 (parámetros): gana en desconocido NO; no pierde en entrenamiento sí

**No pasa nada: la versión final es v1.3-limpers.**