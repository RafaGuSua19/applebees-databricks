# Cola de revisión v2: conducta del empleado

## Resumen

La simulación mostró un punto ciego de la cola v1: casi no detectaba abuso en efectivo. La v2 agrega una señal que compara la semana de cada empleado contra su propia historia. En 7 días simulados encontró **45 de 56 empleado-días sembrados (80 %)**, contra 24 (43 %) de una lista ordenada por monto y 14 (25 %) de la v1, con la misma capacidad de 20 revisiones al día.

## El problema

En efectivo, lo normal ya es ~58 % de descuento porque muchos tickets son cortesías al 100 %. Por eso un descuento de 70 % no se ve raro frente a su referencia, y la señal de **tasa inusual no se activó en ningún ticket sembrado**.

Quitar las cortesías de la referencia tampoco funciona: la tasa empieza a sumar puntos, pero la cola se llena de cortesías reales en efectivo (410 de 420 lugares) y encuentra menos casos sembrados.

## La idea

El abuso de descuentos es **repetitivo**. Un empleado típico aplica 1 descuento MANAGER o WALKOUT al día (el 99 % aplica 9 o menos), mientras que los sembrados aplican 13. La v2 mira, además del ticket, **la semana del empleado frente a su propia historia**: un gerente que siempre aplica muchos descuentos no se marca; uno que cambia de conducta, sí.

## Cambios en `src/jobs/modelo_revision.sql`

1. **Señal "Conducta del empleado"**, para el empleado que aplicó un MANAGER/WALKOUT en el ticket:
   - `n_7d`: sus MANAGER/WALKOUT en los últimos 7 días, contando el día evaluado (la cola se publica al cierre).
   - `base_semanal`: su promedio semanal en los 28 días anteriores a esa semana.
   - **3 puntos** si `n_7d ≥ 12` y `n_7d ≥ 3 × base + 6`; **2 puntos** si `n_7d ≥ 8` y `n_7d ≥ 4 × base + 4`.
2. **Máximo 2 tickets por empleado y día en la cola.** Los demás conservan su puntaje y su posición por monto, pero no entran a la cola. Así los 20 lugares cubren a más empleados.
3. **Puntaje de 0 a 10** (antes 0 a 7). El motivo se explica en texto, por ejemplo: *"Empleado con 33 MANAGER/WALKOUT en 7 días (antes ~1.8 por semana)"*.
4. Columnas nuevas: `puntos_empleado`, `empleado_discrecional`, `descuentos_7d`, `base_semanal` y `orden_empleado`. Versión `contexto-28d-v2-empleado`.

Las señales de la v1 no cambian.

## Resultados en la simulación (21–27 de agosto)

Hay 8 empleados sembrados, uno por tienda, con 4 patrones. Un empleado-día cuenta como encontrado cuando al menos uno de sus tickets sembrados entra a la cola ese día.

| Patrón | Empleado-días | Lista por monto | Cola v1 | **Cola v2** |
|---|---:|---:|---:|---:|
| Efectivo + MANAGER | 14 | 7 | 0 | **14** |
| WALKOUT sin gerente | 14 | 12 | 0 | **14** |
| Autoaprobado + 4 h | 14 | 5 | 14 | **14** |
| Sutil (15–30 % con tarjeta) | 14 | 0 | 0 | 3 |
| **Total** | **56** | **24** | **14** | **45** |

- **Por ticket:** la v2 puso en la cola 85 de los 686 tickets sembrados, la v1 87 y la lista por monto 31. La v1 y la v2 meten casi el mismo número de tickets, pero la v2 los reparte entre más empleados. Para un revisor lo importante es llegar al empleado: el primer ticket lleva al resto.
- **Calidad:** cada día simulado pasó la compuerta de calidad. La demo llegó a 42 archivos y 748,560 tickets, con 0 duplicados y 0 registros en cuarentena.
- **Tiempo:** cada día simulado tarda entre 4 y 5 minutos de punta a punta.

| Día | Tickets generados | Tickets sembrados | Empleado-días en cola v2 |
|---|---:|---:|---:|
| 21 ago | 22,346 | 112 | 6 |
| 22 ago | 18,650 | 92 | 6 |
| 23 ago | 17,796 | 91 | 6 |
| 24 ago | 13,743 | 75 | 7 |
| 25 ago | 14,555 | 102 | 6 |
| 26 ago | 16,149 | 105 | 8 |
| 27 ago | 17,574 | 109 | 6 |

## Efecto en los datos reales (31 jul – 20 ago, 420 lugares)

| | v1 | v2 |
|---|---:|---:|
| Tickets que se conservan de la v1 | 420 | 344 (82 %) |
| Tickets que entran por conducta del empleado | — | 78 |
| Tickets en efectivo en la cola | 10 | 85 |
| Empleados con la señal en 21 días | — | 59 |

La v2 conserva la mayor parte de la cola, empieza a ver el efectivo sin inundarse y la señal es selectiva: unos 7 casos empleado-día al día en toda la cadena. El tope de 2 tickets por empleado se cumple en todas las fechas.

## Pruebas

- La prueba de aceptación incluye un caso con tres tickets del mismo empleado: el tercero queda fuera de la cola y conserva su posición por monto.
- Pasan las pruebas locales y todas las consultas de los widgets del dashboard.
- El histórico real se mantiene igual: 115 archivos y 2,142,846 tickets, con 0 duplicados y 0 en cuarentena.

## Límites

- Los 7 días simulados usan los mismos 8 empleados y patrones con los que se calibraron los umbrales. Esto mide la cobertura de la prueba, no la precisión en operación real; esa se medirá con revisiones humanas en un piloto.
- El patrón sutil casi no se detecta (3 de 14): un descuento pequeño con tarjeta se parece a una promoción.
- Los umbrales (8 y 12 descuentos en 7 días) se calibraron con los últimos 21 días reales y deben revisarse con Operaciones.
- La señal necesita al menos un MANAGER/WALKOUT en el ticket. El abuso con otros códigos de descuento depende de las demás señales.

## Cómo reproducirlo

- Resultados de la simulación contra la lista por monto: `validation/sql/fase3_simulacion.sql` en el esquema de demo.
- Comparación con la v1: correr la versión anterior de `src/jobs/modelo_revision.sql` como CTE en el mismo esquema y cruzarla con `sim_tickets_sembrados` por fecha, tienda y ticket.
- Para el pitch, abrir el dashboard de Simulación en el 27 de agosto, que ya está procesado.
