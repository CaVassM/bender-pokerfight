# Pendientes de Bender

Cosas que no se probaron todavía y que no hay que perder de vista. Marcar con [x] y fecha cuando se cierren.

| # | Pendiente | Cuándo | Estado |
|---|---|---|---|
| 1 | **Verificar P postflop con apuestas en la calle.** | Paso 3 | **[x] 2026-11-11 confirmado** (`pruebas/verificar_pozo.py`: preflop 220/220, flop 51/51, turn 27/27, river 15/15). |
| 2 | **Caída de socket con la mesa real.** Proxy TCP local entre Bender y `bin/mesa` que corta la conexión a mitad de mano (`pruebas/robustez.py --escenario proxy`). | Antes de la entrega | **[x] 2026-11-11.** Corte tras reenviar la solicitud (3 cortes) y corte antes de reenviarla (2 cortes × 3 repeticiones): Bender reconectó solo, mismo proceso y mismo token, misma silla (4) y saldo; 0 errores / 0 acciones inválidas; la mesa terminó todas sus rondas; el camino "sin cartas de esta mano: acción segura" se ejerció (4 decisiones). |
| 3 | **Relanzamiento de Bender a mitad de mano, en vivo** (`pruebas/robustez.py --escenario relanzar`). | Antes de la entrega | **[x] 2026-11-11.** 3 kills con una decisión pendiente (mesa de 150 manos): cada proceso nuevo retomó la silla 4 y su saldo y siguió jugando; 0 errores; la mesa terminó. Matiz: en estas pruebas el proceso nuevo entró en la mano siguiente (la mesa ya había jugado la acción segura por él), así que el camino "sin cartas" se ejercita en la prueba del proxy, no aquí. |
| 4 | **Horas conectado en silencio**, en el servidor de pruebas (`docs/servidor-practica.md`). El socket no tiene timeout de lectura y usa keepalive TCP, pero no se ha medido. | Antes de la entrega | [ ] |
| 5 | **Ejemplo de §2.1 (media/aire).** | Paso 4 | **[x] 2026-11-11 cerrado** con la lista fija de 48 clases del equipo. |
| 6 | **Reglas de solo valor (§1.11).** | Paso 4 | **[x] activadas por defecto.** Apagarlas contra rivales que se retiran mucho no mejora. |
| 7 | **Meta "ganarle a base".** | Pasos 3-5 | **[x] 2026-11-11 en heads-up:** +29,6 ±14,7 bb/100 con 12 000 manos (commit 6f3004a8). Sin explotación +37,6 ±16,6 (la explotación no suma contra `base`). Mesas de 5: sin muestra suficiente para concluir (±130). |
| 8 | **Velocidad para la Capa 3 (manos/s).** | Antes de la Capa 3 | **[~] parcial:** el orden por fuerza de §1.9 usa repartos compartidos por board (mismo estimador, ~35 % menos tiempo; flop 35 ms de mediana con la máquina quieta). Techo medido ~230 manos/s con 32 mesas en paralelo. Falta bajar el costo restante de Bender si se quiere más. |
| 9 | **Capa 2 pierde frente a `conservador`.** | Paso 5 | **[x] resuelto** con las plantillas calibradas (`conservador` pasó de +77 a +263 bb/100 en HU). |
| 10 | **Recalibrar `m` y el prior de tipos con la población REAL** cuando abra el servidor de pruebas. Hoy están calibrados solo con los 6 bots de entrenamiento del kit (m: VPIP 0,455, PFR 0,143, sigue chica 0,692, sigue grande 0,545; prior .06/.53/.18/.06/.17; tabla preflop F/C/R y plantillas postflop de TAG y station). Registrar las estadísticas de los bots de otros equipos y volver a correr `calibrar.py` y `calibrar_plantillas.py` (el segundo necesita historial con cartas: pedir al servidor o usar mesas locales). | Cuando abra el servidor de pruebas | [ ] |
| 11 | **Memoria entre rondas.** Campaña de 12 × 10 mesas × 50 manos: antes de la explotación CON − SIN = −3,2 ±73,8 bb/100 (`camp-1`); con la explotación −34,6 ±83,8 (`camp-2`). Sin efecto detectable (y el punto estimado es negativo en las mesas 6-10, −90 ±90: ruido o un posible daño; sospechar si se repite). El `id_jugador` sí es estable por token (4 archivos por campaña). Los bots del kit reinician su proceso en cada mesa (en el torneo real no). Repetir con más campañas y, idealmente, rivales que se queden conectados. | Antes de la entrega | [ ] |
| 13 | **Filtro por tipo de §3.4 ("no farolear a station/maníaco/aleatorio")** apagado por defecto (`explotacion.filtros_tipo`): con él `conservador` pasa de +247 a +41 bb/100. Decisión del usuario. | Decisión del usuario | [ ] |
| 12 | **Diferencia entre `.tex` y `params.py`** (columna "Aleatorio", TAG calibrado, etc.). | Aviso al usuario | **[x] 2026-11-11** el `.tex` se actualizó (tag `v1-probabilistico`); `DESVIACIONES.md` solo lista lo que el `.tex` no cubre. |
| 14 | **Evaluación de reserva (darwin y novato), UNA vez, con `v1-probabilistico`.** HU (20 parejas por rival × 150 manos): darwin +88,3 ±40,2; novato +24,9 ±20,0; ambos +56,6 ±23,0 (entrenamiento: +188 ±36). Mesas de 5 (60 mesas × 50 manos, pool darwin/novato/base/estadistico/bandido/espia): +74,3 ±64,9 (entrenamiento +113 ±137; compatibles). No se cambió nada en base a esto. | Hecho | **[x] 2026-11-11** |
| 15 | **Corrida grande de mesas de 5 con los 8 bots (incl. darwin y novato), asientos rotando**, para IC ≤ ±40 bb/100. Desviación por mesa de 50 manos: 256 (205-367 en otras corridas) → 165-340 mesas bastan; propuesta 600 mesas (≈ 50-60 min con 6 en paralelo, IC global ≈ ±25-30, por rival ≈ ±35-45). Espera confirmación del usuario. | Esta noche | [ ] |
| 16 | **Varianza alta:** Bender termina con 0 fichas en 15 de 60 mesas de 50 manos (25 %) pese a media positiva. Tenerlo presente al diseñar la Capa 3 y la política de riesgo. | Capa 3 | [ ] |

## Reglas permanentes
- **Nada fuera de `bender/`** (ni `pkg/`, `internal/`, `cmd/`, `bots/`, `docs/`, `torneo-go.json`). Solo se permite generar `bin/` y `resultados/`.
- **Al cerrar cada paso:** commit en `bender/` y, en la raíz del kit, `git status` + `git diff --stat` (deben mostrar solo `bender/` sin rastrear).
- **Higiene de evaluación (2026-11-11):** ninguna evaluación se corre desde la carpeta donde se edita. Se usa `pruebas/evaluar_fijo.py`, que corre el script (`evaluar.py`, `campana.py`...) desde un `git worktree` de un commit fijo (fuera del kit, en `../bender_eval/<hash>/`), se niega si hay cambios sin commitear y deja el hash del commit en el JSON del resultado. Así se puede seguir editando mientras corre una medición, y toda cifra es reproducible con su commit.

## Carpeta de trabajo
Desde el paso 3 se trabaja en el clon limpio del kit (`pokerfight-arena-participantes`), con `bender/` como repo propio (`bender/.git`). La carpeta del zip original (`pokerfight-arena-participantes-main`) queda sin tocar.

## Lección de proceso
Editar código de `bender/` mientras corre una evaluación contamina la medición (pasó con `capa1-v4`, descartada). Resuelto con la regla del worktree.

Procesos huérfanos (2026-11-11): en Windows `sys.executable` del venv lanza un hijo, así que `Popen.kill()` deja vivo el proceso de Bender. Una corrida que falló a mitad (novato sin binario en las mesas) dejó 5 Benders huérfanos que ocuparon los puertos de la corrida siguiente y contaminaron sus resultados (21 de 60 mesas «descartadas»). Resuelto: `evaluar.py` y `robustez.py` matan el árbol con `taskkill /T` aunque falle el lanzamiento. Antes de leer una evaluación, comprobar que no queda ningún `python.exe` de `bender_eval` vivo y que no hay mesas descartadas.
