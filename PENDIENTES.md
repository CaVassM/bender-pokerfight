# Pendientes de Bender

Cosas que no se probaron todavía y que no hay que perder de vista. Marcar con [x] y fecha cuando se cierren.

| # | Pendiente | Cuándo | Estado |
|---|---|---|---|
| 1 | **Verificar P postflop con apuestas en la calle.** Preflop `pozo == suma(apuesta_ronda)` (66/66), pero postflop solo se vieron calles sin apuestas. Comprobar que `estado.pozo` incluye las apuestas de la calle en curso (definición de $P$, §0 del .tex). | Paso 3 (cuando Bender ya apueste y vea apuestas postflop) | [ ] |
| 2 | **Caída de socket con la mesa real.** Un proxy TCP local entre Bender y la mesa que corte la conexión a mitad de mano; comprobar que Bender reconecta dentro del mismo proceso y retoma silla y fichas. Hoy solo está probado con una mesa falsa (prueba unitaria). | Antes de la entrega | [ ] |
| 3 | **Relanzamiento de Bender a mitad de mano, en vivo.** El kill de la prueba cayó entre manos; falta que caiga con una mano en curso para ejercitar el camino "sin cartas de esta mano: acción segura". Hoy solo tiene prueba unitaria. | Antes de la entrega | [ ] |
| 4 | **Horas conectado en silencio**, en el servidor de pruebas (`docs/servidor-practica.md`). El socket no tiene timeout de lectura y usa keepalive TCP, pero no se ha medido. | Antes de la entrega | [ ] |

## Regla permanente
No modificar nada fuera de `bender/` (ni `pkg/`, `internal/`, `cmd/`, `bots/`, `docs/`, `torneo-go.json`). Solo se permite generar `bin/` y `resultados/`. Antes de cerrar cada paso: `git status` y `git diff --stat` en la raíz (ver nota en el reporte si la raíz no es un repositorio).
