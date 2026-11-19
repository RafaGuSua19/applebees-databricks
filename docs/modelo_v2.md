# Cola de revisión v2: conducta del empleado

## Qué encontró la simulación

Con 2 días simulados y 204 tickets sembrados, la v1 metió a la cola 23 tickets, todos del patrón "autoaprobado + 4 h". La señal de **tasa inusual no se activó en ningún ticket sembrado**. En efectivo, lo normal ya es ~58 % de descuento (muchas cortesías al 100 %), así que un 70 % no se ve raro.

Sacar las cortesías de la referencia no funciona: la tasa empieza a sumar puntos, pero la cola se llena de cortesías reales en efectivo (410 de 420 lugares) y detecta menos sembrados (11 en vez de 23).

## La idea

El abuso de descuentos es **repetitivo**: un empleado que empieza a aplicar MANAGER o WALKOUT muchas veces. Un empleado típico aplica 1 al día (p99 = 9); los sembrados, 13. En lugar de mirar solo el ticket, la v2 mira también **la semana del empleado frente a su propia historia**.

## Cambios en `src/jobs/modelo_revision.sql`

1. **Nueva señal "Conducta del empleado"**, para el empleado que aplicó un MANAGER/WALKOUT en el ticket:
   - `n_7d` = sus MANAGER/WALKOUT en los últimos 7 días, contando el día evaluado (la cola se publica al cierre).
   - `base_semanal` = su promedio semanal en los 28 días anteriores a esa semana.
   - **3 puntos** si `n_7d ≥ 12` y `n_7d ≥ 3 × base + 6`.
   - **2 puntos** si `n_7d ≥ 8` y `n_7d ≥ 4 × base + 4`.

   Al compararlo con su propia historia, un gerente que siempre aplica muchos descuentos no se marca; uno que **cambia de conducta**, sí.
2. **Máximo 2 tickets por empleado y día en la cola.** Los siguientes tickets conservan su score y posición por importe, con prioridad de cola nula. Así 20 lugares cubren más empleados distintos en lugar de 15 tickets de la misma persona.
3. **Puntaje de 0 a 10** (antes 0 a 7). El motivo se explica en texto: *"Empleado con 33 MANAGER/WALKOUT en 7 días (antes ~1.8 por semana)"*.
4. Columnas nuevas: `puntos_empleado`, `empleado_discrecional`, `descuentos_7d`, `base_semanal`, `orden_empleado`. Versión `contexto-28d-v2-empleado`.

Las señales de la v1 no cambian.

## Resultados de referencia

**Simulación** (`applebees_demo`, 21–22 de agosto, 8 empleados sembrados en dos días = 16 empleado-días). Se reprodujo en modo lectura antes de evaluar los siguientes días.

| | Lista por monto | Cola v1 | **Cola v2** |
|---|---:|---:|---:|
| Empleado-días sembrados encontrados | 9 / 16 | 4 / 16 | **12 / 16** |
| Efectivo + MANAGER | 3 / 4 | 0 / 4 | **4 / 4** |
| WALKOUT sin gerente | 3 / 4 | 0 / 4 | **4 / 4** |
| Autoaprobado + 4 h | 3 / 4 | 4 / 4 | **4 / 4** |
| Sutil (15–30 % con tarjeta) | 0 / 4 | 0 / 4 | 0 / 4 |
| Tickets sembrados en la cola | 13 | 23 | 23 |

El total de 23 tickets sembrados coincide entre versiones. La v2 distribuye esos tickets entre más empleado-días. Para un revisor, encontrar al empleado es lo que importa: el primer ticket lleva al resto.

**Datos reales** (verificados del 31 de julio al 20 de agosto, con 420 lugares por versión).

| | v1 | v2 |
|---|---:|---:|
| Tickets que se conservan de la v1 | 420 | 344 (82 %) |
| Tickets que entran por conducta del empleado | — | 78 |
| Tickets en efectivo en la cola | 10 | 85 |
| Empleados con la señal en 21 días | — | 59 |

La comparación del histórico confirmó 344 tickets en ambas listas y 85 tickets en efectivo en v2 frente a 10 en v1. El máximo de dos tickets por empleado identificado se cumplió en todas las fechas publicadas.

## Límites

- El patrón "sutil" (pocos puntos de descuento con tarjeta) sigue sin detectarse. Es razonable: se parece a una promoción.
- Los umbrales (8 y 12 en 7 días) se calibraron con los últimos 21 días reales; se deben revisar con Operaciones.
- La señal necesita al menos un MANAGER/WALKOUT en el ticket; el abuso con otros códigos de descuento depende de las demás señales.

## Despliegue y pruebas

- [Republicación de `phase3`](https://dbc-eb170ead-6845.cloud.databricks.com/jobs/1077728338396415/runs/61457160621924?o=7474659154935244) y [republicación de `demo`](https://dbc-eb170ead-6845.cloud.databricks.com/jobs/737955808701802/runs/1112983107095425?o=7474659154935244) con `contexto-28d-v2-empleado`. Se publicaron las tablas antes de actualizar los dashboards.
- [Aceptación en Databricks](https://dbc-eb170ead-6845.cloud.databricks.com/jobs/836429566572761/runs/95271018841802?o=7474659154935244). Pasaron los escenarios de ventana y ranking. El test de tres tickets de la misma persona confirma que el tercero queda fuera de la cola y conserva su posición por importe.
- Las 15 pruebas locales y las 72 consultas de widgets terminaron sin errores. El histórico real conservó 115 archivos y 2,142,846 tickets, con cero duplicados y cero registros en cuarentena.
- El permiso `CAN_MANAGE_RUN` se configura en el recurso del job de simulación. El job sigue ejecutándose con la identidad de quien lo despliega. Los parámetros de ruta del notebook se validan contra el volumen oficial y el volumen y esquema dedicados a demo.
