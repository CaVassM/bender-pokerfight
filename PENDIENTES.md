# Pendientes de Bender

Cosas que no se probaron todavía y que no hay que perder de vista. Marcar con [x] y fecha cuando se cierren.

| # | Pendiente | Cuándo | Estado |
|---|---|---|---|
| 1 | **Verificar P postflop con apuestas en la calle.** | Paso 3 | **[x] 2026-11-11 confirmado** (`pruebas/verificar_pozo.py`: preflop 220/220, flop 51/51, turn 27/27, river 15/15). |
| 2 | **Caída de socket con la mesa real.** Un proxy TCP local entre Bender y la mesa que corte la conexión a mitad de mano; comprobar que Bender reconecta dentro del mismo proceso y retoma silla y fichas. Hoy solo está probado con una mesa falsa (prueba unitaria). | Antes de la entrega | [ ] |
| 3 | **Relanzamiento de Bender a mitad de mano, en vivo.** El kill de la prueba cayó entre manos; falta que caiga con una mano en curso para ejercitar el camino "sin cartas de esta mano: acción segura". Hoy solo tiene prueba unitaria. | Antes de la entrega | [ ] |
| 4 | **Horas conectado en silencio**, en el servidor de pruebas (`docs/servidor-practica.md`). El socket no tiene timeout de lectura y usa keepalive TCP, pero no se ha medido. | Antes de la entrega | [ ] |
| 5 | **Ejemplo de §2.1 (media/aire).** | Paso 4 | **[x] 2026-11-11 cerrado.** Con la lista fija de 48 clases del equipo (340 combos) sale 43 / 45 / 171 ±5; el test ya no es `xfail`. |
| 6 | **Reglas de solo valor (§1.11).** | Paso 4 | **[x] activadas por defecto** (decisión del equipo). Re-medido con la Capa 2 contra rivales que se retiran mucho (conservador, bandido, base): apagarlas no mejora (conservador −0,8 ±5,5; bandido −36 ±21; base +21 ±30). Se mantienen activas. |
| 7 | **Meta "ganarle a base".** | Pasos 3-4 | Heads-up con Capa 1 + Capa 2: +37,0 ±28,0 bb/100 (10 semillas, 3 000 manos). Con 12 000 manos y solo Capa 1 hizo falta más muestra para decidir; repetir con la versión final. |
| 8 | **Velocidad para la Capa 3 (manos/s).** El orden por fuerza de §1.9 (flop y turn) cuesta ~100 ms por decisión con rangos anchos; Python puro. Ver reporte del paso 4: opciones para bajarlo (menos simulaciones por combo, proxy por rank en el flop, numpy). | Antes de la Capa 3 | [ ] |
| 9 | **Capa 2 pierde frente a `conservador`** (−34 ±9 bb/100 emparejado vs Capa 1 sola): el tipo "station" cree que paga todo y `conservador` se retira ante apuestas grandes (sigue_grande 0,28). Lo corrige §3.3 (θ con "sigue chica/grande") en el paso 5. | Paso 5 | [ ] |

## Regla permanente
No modificar nada fuera de `bender/` (ni `pkg/`, `internal/`, `cmd/`, `bots/`, `docs/`, `torneo-go.json`). Solo se permite generar `bin/` y `resultados/`. Antes de cerrar cada paso: commit en `bender/` y, en la raíz del kit, `git status` + `git diff --stat` (deben mostrar solo `bender/` sin rastrear).

## Carpeta de trabajo
Desde el paso 3 se trabaja en el clon limpio del kit (`pokerfight-arena-participantes`), con `bender/` como repo propio (`bender/.git`). La carpeta del zip original (`pokerfight-arena-participantes-main`) queda sin tocar.

## Lección de proceso
No editar código de `bender/` mientras corre una evaluación: cada proceso de Bender importa el código al arrancar y una edición a mitad contamina la medición (pasó con `capa1-v4`, descartada).
