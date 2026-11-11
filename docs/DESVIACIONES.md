# Capa 1: lo que el código hace y el .tex no dice (o dice distinto)

Fuente de verdad: `bender_formulas.tex`. Esta lista es lo que se decidió al implementarlo; cada punto
está marcado con su sección y con lo que hay que cambiar si se quiere seguir el .tex al pie de la letra.

| # | Dónde | Qué hace el código | Por qué |
|---|---|---|---|
| 1 | §1.2 reloj | Siempre corre un bloque mínimo de 64 simulaciones, aunque T_max sea 0. Si los rangos no pueden convivir (cartas muertas) devuelve `imposible` y se cae a manos al azar. | Con T_max=0 no habría estimación; sin tope de intentos, un bucle infinito. |
| 2 | §1.7 / §3.3 c_i | `c_i` sale del **rango** del rival (postflop: plantilla §2.1 escalada a x; preflop: parte del rango dentro del umbral de fuerza de c_pob(x)). Solo sin rango se usa c(x) de §1.7. | §3.3 dice que θ_base de c_i es el c del rango. Con c(x) siempre, Bender re-subía hasta all-in con basura contra quien acababa de re-subir (−510 000 fichas en 1 800 manos heads-up). |
| 3 | §1.9 e' | `e'` se calcula **por tamaño de apuesta**: contra el rango que paga esa apuesta (preflop, la fracción c_i más fuerte de su rango). | Con un solo e' (calculado para media apuesta) el all-in de 100 bb parecía +EV: pagaba "el 89 %" del rango cuando en realidad paga ≈24 %. |
| 4 | §1.9 multiway | Con varios rivales, pagan los `n = max(1, round(Σ c_i))` de mayor c_i y e' se calcula contra sus rangos de pago. | El .tex fija A' (rival con más fichas) pero no cómo sale e' en multiway. |
| 5 | §1.9 A | Si el rival con más fichas no puede cubrir todo, la parte sobrante vuelve a Bender (A_ef = min(A, fichas que el rival puede igualar)). | Fichas no igualadas no se pierden (docs/reglas.md). Coincide con el ejemplo del .tex cuando alcanzan. |
| 6 | §1.6 call corto | Si el saldo no alcanza para igualar, EV usa lo que se puede cubrir; lo no cubierto vuelve a su dueño. | docs/reglas.md. |
| 7 | §1.5 BB con opción | Si nadie subió y Bender es BB (C=0), no abre por tabla: decide con el menú EV (pasar o subir). Sin limp para el resto. | El .tex solo define apertura para quien tiene que pagar algo. |
| 8 | §1.5 apertura con limpers | Abre siempre a 2,5 bb (no suma una ciega por limper). | Literal del .tex. |
| 9 | §2.8 rangos de rivales | Quien sube preflop: top % de su posición (§1.5); quien re-sube: el top % se multiplica por 0,45 por cada re-subida (mín. 3 %); quien solo paga: w=1 en VPIP (0,30) sin PFR, 0,3 en el top del PFR; quien no actuó: mano al azar. Sin Capa 2 (ρ=0). | El .tex deja "se estrecha con la plantilla" sin números preflop. `estrecha_por_subida` y `min_pct_rango` son parámetros propios. |
| 10 | §2.2 tipo sin datos | Rival sin datos = fila "Promedio / TAG" pura (π={'tag':1}), no la mezcla del prior. | El ejemplo de §2.1 usa esa fila (c=0,37). |
| 11 | §1.11 variantes | `allin_profundo_solo_valor` y `solo_valor_sobre_apuesta`: **apagadas**; solo se usan si se pasa un JSON de parámetros. | Son cambios de regla: decide el usuario. |
| 12 | ranking de 169 clases | Equity contra mano al azar con 4 M de simulaciones por clase. Los bordes de top-% del .tex (14,3 / 18,9 / 25,5 / 43,3) caen a 2-6 combos de un borde de clase. | Decenas de clases a menos de 0,05 puntos entre sí: el orden exacto no se puede reproducir. |
