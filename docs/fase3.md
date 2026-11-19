# Fase 3 · Revisión diaria de descuentos

**Pregunta de negocio:** ¿qué tickets con descuento debe revisar primero Operaciones cada día, con capacidad para 20 revisiones, y qué evidencia explica su prioridad?

Partimos del pipeline de Fase 2, agregamos un modelo que puntúa cada ticket y mostramos la evidencia en un dashboard de Databricks. El monto de un ticket en la cola es el descuento registrado; la revisión decide si el caso es legítimo, requiere acción o no tiene evidencia suficiente.

## De dónde partimos

La [validación de Fase 2](validacion.md) cubre 2,142,846 tickets de 127 tiendas (28 abr – 20 ago 2026): $3.02 M de descuento sobre $87.32 M de venta bruta (3.46 %).

| Hallazgo | Qué hacemos con él |
|---|---|
| El efectivo concentra 55.2 % del descuento y solo 17.5 % de la venta | La forma de pago define el grupo de comparación de cada ticket |
| Los tickets abiertos 4 h o más descuentan 21.24 %, contra 3.25 % del resto | La duración suma un punto |
| To Go descuenta 12.18 %, contra 3.76 % en In-Store | El canal define el grupo de comparación |
| 34 pares empleado–tienda en riesgo alto (de 2,959) con el score de Fase 2 | La cola baja al nivel de ticket, que es donde actúa un revisor |

## Cómo funciona el modelo

1. Se puntúa cada ticket con venta bruta y descuento positivos. Su tasa es descuento ÷ venta bruta.
2. Para cada fecha se calcula la media y la desviación estándar de las tasas en los **28 días anteriores**, en tickets de la misma tienda, canal y forma de pago (≥ 50 tickets en ≥ 7 días). Si la tienda no alcanza, se usa la cadena con el mismo canal y pago (≥ 200 tickets). Si tampoco, el ticket queda como "historial insuficiente" y la tasa no suma puntos. La desviación tiene un piso de 2 puntos porcentuales.
3. Se suman los puntos (0 a 10):

| Señal | Puntos |
|---|---:|
| Tasa ≥ 3 desviaciones arriba de su referencia y ≥ 10 pp de diferencia | 3 |
| Si no, ≥ 2 desviaciones y ≥ 8 pp | 2 |
| Autoaprobación (el mismo empleado aplica y autoriza) | 2 |
| MANAGER o WALKOUT sin gerente | 1 |
| Ticket abierto 4 h o más | 1 |
| El empleado lleva muchos MANAGER/WALKOUT esta semana frente a su propia historia (v2) | 3 o 2 |

4. La cola de cada día toma los **20 tickets con más puntos (mínimo 2)**, con máximo 2 por empleado. Los empates se ordenan por monto. Cada ticket guarda también su posición por monto para comparar.

**Ejemplo:** un ticket con $40 de descuento sobre $100 (40 %), en un contexto donde lo normal es 10 %, con autoaprobación y 245 minutos abierto, suma 3 + 2 + 1 = **6 puntos**. Queda primero en la cola aunque por monto sería tercero.

Las reglas de la conducta del empleado y sus resultados están en [modelo_v2.md](modelo_v2.md).

## Resultados

**Datos reales, últimos 21 días (31 jul – 20 ago), 20 lugares por día:**

- 46,387 candidatos. El 99.24 % tuvo referencia válida: 40,686 de su tienda, 5,347 de la cadena y 354 sin historial suficiente.
- De 420 lugares, la cola v1 y la lista por monto coinciden solo en **49**; los otros **371** son tickets que ordenar por monto no habría visto. 413 de los tickets de la cola recibieron puntos por tasa inusual.
- La v2 conserva 344 de esos 420 tickets y agrega 78 por conducta del empleado.

**Simulación, 7 días (21–27 ago):** la v2 encontró **45 de 56 empleado-días sembrados (80 %)**, contra 24 (43 %) de la lista por monto y 14 (25 %) de la v1. Detalle en [modelo_v2.md](modelo_v2.md) y [demo_fase3.md](demo_fase3.md).

**Pruebas de funcionamiento:**

- Una segunda corrida sin archivos nuevos dejó idénticos los conteos y las huellas de Bronze (2,142,846 filas), KPIs (130,259) y modelo (268,580).
- Pasaron las regresiones con datos sintéticos, los controles sobre el histórico y los tres notebooks de análisis.
- Prueba con dos archivos sintéticos: Bronze pasó de **1 → 3 → 3** filas tras dos llegadas y una reejecución. Un ticket con tres advertencias entró conservando sus $10.00 de descuento, y un registro sin llave quedó en cuarentena.

## Ingesta, calidad y publicación

- **Entrada:** Auto Loader lee los JSON diarios en `<source_path>/facts/checks/brand=rmh/dt=AAAA-MM-DD/`. Cada archivo nuevo debe tener ruta nueva, y la fecha de negocio debe coincidir con la carpeta.
- **Advertencias:** un campo nuevo, un artículo sin ID o una propina ausente no tiran el ticket. Entra a Silver con `_dq_warnings` y se conservan sus importes válidos. Si falta la propina, queda como desconocida.
- **Cobertura:** la conciliación se calcula sobre los tickets con propina conocida, y el dashboard muestra la conciliación y su cobertura por separado.
- **Cuarentena:** un error de formato, llave, fecha o importe esencial deja el registro en Bronze con su JSON y su motivo. La compuerta bloquea la publicación; mientras tanto sigue visible la última cola publicada.
- **Ejecución:** `refresh_pipeline → data_quality_gate → publish_review_queue`. El score se recalcula para todas las fechas, así que una llegada tardía puede cambiar los días siguientes de su ventana.
- **Horario:** propuesto a las 06:00 `America/Chicago`. Está pausado hasta acordar con Operaciones la hora de entrega del POS.

## Dashboard

1. **Descuentos:** tickets, venta, descuento y tasa, con barras por forma de pago y canal. Los filtros globales (fecha, tienda, canal, pago y datos reales o simulados) se mantienen entre pestañas.
2. **Cola de revisión:** los tickets del día con sus motivos, el desglose de puntos, la tasa frente a su referencia, la posición por monto y si tienen advertencia de datos.
3. **Calidad y frescura:** último día procesado, última publicación de la cola, advertencias, cuarentena y cobertura de conciliación.
4. **Simulación** (solo en el target `demo`): días simulados, tickets sembrados y cuántos encuentra la cola.

El dashboard no muestra el JSON original ni nombres de empleados, y se publica con los permisos de datos de quien lo despliega.

## Alcance para la final

| Entregable | Evidencia |
|---|---|
| Pipeline funcional | Llegada de un día nuevo en vivo, reejecución sin cambios y tiempos medidos |
| Calidad y trazabilidad | Una advertencia que conserva el ticket, una cuarentena y la compuerta deteniendo la publicación |
| Insights | Efectivo, duración y canal; cuánto cambia la cola frente a ordenar por monto |
| Dashboard y KPIs | Las cuatro páginas con filtros globales |
| Solución analítica | Cobertura de la cola v2 sobre abuso sembrado y comparación con la lista por monto |
| Recomendaciones | Revisar primero autorizaciones discrecionales, autoaprobaciones y tickets de 4 h+ |
| Documentación técnica | Bundle, pruebas, definición del score, supuestos y respuesta ante fallas |
| Presentación ejecutiva | Recorrido de un ticket de la llegada a la cola, y resultados |

**Piloto propuesto:** cada caso revisado se etiqueta como accionable, legítimo o evidencia insuficiente, con un checklist común (autorización, elegibilidad de la promoción, momento del descuento, cierre). El revisor no ve de qué lista viene el caso. La medida de éxito es **casos accionables por cada 20 revisiones**, comparando la cola contra la lista por monto.

## Archivos de esta fase

| Archivo | Cambio |
|---|---|
| `src/transformations/bronze/bronze_checks.py` | Advertencias recuperables y validación de capacidad decimal |
| `src/transformations/silver/st_checks_cleaned.py`, `st_details_cleaned.py` | Conservan advertencias, propina desconocida y líneas sin ID |
| `src/transformations/gold/mv_calidad_datos.sql`, `mv_incidencias_ingesta.sql` | Cobertura, conteos de calidad y resumen de incidencias por archivo |
| `src/jobs/modelo_revision.sql`, `publicar_revision.py` | Score, motivos, ranking por monto y publicación después de la compuerta |
| `src/simulacion/` | Simulador de días con abuso sembrado |
| `databricks.yml`, `resources/jobs/*.yml` | Tarea de publicación, targets `phase3` y `demo`, job de simulación |
| `resources/dashboards/revision_descuentos.lvdash.json` | Dashboard AI/BI |
| `tests/`, `validation/sql/fase3_*.sql` | Regresiones, prueba de llegadas, idempotencia, comparación de listas y simulación |

```bash
python3 scripts/validate_local.py
databricks bundle deploy -t phase3 --var dashboard_warehouse_id=ID_DEL_WAREHOUSE
databricks bundle run daily_orchestration_job -t phase3 --var dashboard_warehouse_id=ID_DEL_WAREHOUSE
databricks bundle run validation_job -t phase3 --var dashboard_warehouse_id=ID_DEL_WAREHOUSE
```

Un target nuevo vuelve a leer todo el histórico desde el origen. En un esquema que ya tiene checkpoints, aplicar el cambio de admisión a filas antiguas requiere un full refresh.
