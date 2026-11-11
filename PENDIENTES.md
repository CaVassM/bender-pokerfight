# Pendientes de Bender

Cosas que no se probaron todavía y que no hay que perder de vista. Marcar con [x] y fecha cuando se cierren.

| # | Pendiente | Cuándo | Estado |
|---|---|---|---|
| 1 | **Verificar P postflop con apuestas en la calle.** ¿`estado.pozo` incluye las apuestas de la calle en curso (definición de $P$, §0 del .tex)? | Paso 3 | **[x] 2026-11-11 confirmado.** `pruebas/verificar_pozo.py` sobre una mesa local con Bender apostando: `pozo == (pozo al abrir la calle) + Σ apuesta_ronda` en preflop 220/220, flop 51/51, turn 27/27, river 15/15. |
| 2 | **Caída de socket con la mesa real.** Un proxy TCP local entre Bender y la mesa que corte la conexión a mitad de mano; comprobar que Bender reconecta dentro del mismo proceso y retoma silla y fichas. Hoy solo está probado con una mesa falsa (prueba unitaria). | Antes de la entrega | [ ] |
| 3 | **Relanzamiento de Bender a mitad de mano, en vivo.** El kill de la prueba cayó entre manos; falta que caiga con una mano en curso para ejercitar el camino "sin cartas de esta mano: acción segura". Hoy solo tiene prueba unitaria. | Antes de la entrega | [ ] |
| 4 | **Horas conectado en silencio**, en el servidor de pruebas (`docs/servidor-practica.md`). El socket no tiene timeout de lectura y usa keepalive TCP, pero no se ha medido. | Antes de la entrega | [ ] |
| 5 | **Ejemplo de §2.1 (media/aire).** Con el ranking propio el top 25 % da 43 / 51 / 162 (fuertes / medios / aire) y el .tex dice 43 / 45 / 171; el test `test_ejemplo_2_1_medios_y_aire_dentro_de_5_combos` está como `xfail`. | Decisión del usuario | [ ] |
| 6 | **Variantes de regla de §1.11** (`allin_profundo_solo_valor`, `solo_valor_sobre_apuesta`): implementadas y apagadas por defecto; medidas en el paso 3. | Decisión del usuario | [ ] |
| 7 | **Meta "ganarle a base" en heads-up.** Con las reglas del .tex: −10,5 ±15,5 bb/100 (12 000 manos); con las dos variantes: +6,4 ±17,4. Hoy está en torno a empate. La Capa 2 (huella de `base`) es el camino previsto. | Paso 4 | [ ] |

## Regla permanente
No modificar nada fuera de `bender/` (ni `pkg/`, `internal/`, `cmd/`, `bots/`, `docs/`, `torneo-go.json`). Solo se permite generar `bin/` y `resultados/`. Antes de cerrar cada paso: commit en `bender/` y, en la raíz del kit, `git status` + `git diff --stat` (deben mostrar solo `bender/` sin rastrear).

## Carpeta de trabajo
Desde el paso 3 se trabaja en el clon limpio del kit (`pokerfight-arena-participantes`), con `bender/` como repo propio (`bender/.git`). La carpeta del zip original (`pokerfight-arena-participantes-main`) queda sin tocar.
