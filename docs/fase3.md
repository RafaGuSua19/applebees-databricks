# Fase 3 · Revisión diaria de descuentos

**Pregunta de negocio.** ¿Qué tickets con descuento debe revisar primero Operaciones cada día, dada una capacidad inicial de 20 revisiones, y qué evidencia explica su prioridad?

El entregable de esta fase es la propuesta y su alcance para la final. El prototipo toma el pipeline de Fase 2, agrega un modelo por ticket y presenta la evidencia en un dashboard de Databricks. Las cifras históricas y los resultados de un futuro piloto tienen significados distintos. El monto asociado a un ticket es el descuento registrado. Una revisión puede concluir que el caso es legítimo, requiere una acción o tiene evidencia insuficiente.

## Evidencia de partida

La [validación de Fase 2](validacion.md) documenta 2,142,846 tickets de 127 tiendas, 28 de abril a 20 de agosto de 2026. Registró $3.02 M en descuentos sobre $87.32 M en venta bruta (3.46%).

| Hallazgo | Denominador y decisión |
|---|---|
| Efectivo concentra 55.2% del descuento y 17.5% de la venta bruta | Participación del efectivo en cada total. Revisar el circuito de autorización en los casos señalados. |
| Tickets abiertos ≥4 h tienen tasa de 21.24%, frente a 3.25% para el resto | Descuento / venta bruta dentro de cada grupo. Revisar cierre y momento de autorización. |
| To Go tiene tasa de 12.18%, frente a 3.76% en In-Store | Descuento / venta bruta por canal. Incorporar el canal al grupo de referencia. |
| 34 pares de empleado y tienda aparecen en el nivel alto del score anterior, de 2,959 elegibles | Regla histórica por empleado y tienda. La cola nueva prioriza tickets individuales. |

La guía de Fase 2 preliminar y el EDA incluyen un universo de 2,960. El informe de validación y la presentación final de Fase 2 registran 2,959 pares elegibles. Usamos el valor validado y las definiciones contables de la entrega.

## Cómo funciona el modelo

1. Se puntúa una fila por ticket admitido con bruto y descuento positivos. Su tasa es descuento total entre venta bruta. Las líneas de descuento positivas explican autoaprobación y ausencia de gerente para MANAGER/WALKOUT.
2. Para cada fecha, se aprende la media y desviación estándar poblacional de las tasas individuales en los **28 días calendario anteriores**. Las tasas de referencia se limitan a 100% al estimar la distribución. El valor original del ticket sigue visible y se usa para su desviación. La desviación estándar tiene un piso de 2 puntos porcentuales para cohortes uniformes.
3. Se busca una referencia de la misma tienda, canal y forma de pago con ≥50 tickets descontados en ≥7 días con descuentos. Cuando no alcanza, se usa la cadena para el mismo canal y pago con ≥200 tickets en ≥7 días con descuentos. Con historia insuficiente, se muestra el estado y los puntos contextuales quedan en cero.
4. Se explica cada punto con la evidencia observable. El puntaje toma un valor de 0 a 7 y cada ticket tiene una posición por score y otra por importe.

| Señal | Puntos |
|---|---:|
| Tasa al menos 3 desviaciones arriba de su media y brecha ≥10 puntos porcentuales | 3 |
| Tasa al menos 2 desviaciones arriba de su media y brecha ≥8 puntos porcentuales | 2 si no aplica la regla anterior |
| Algún descuento positivo con autoaprobación identificada | 2 |
| MANAGER o WALKOUT positivo sin gerente identificado | 1 |
| Duración de al menos cuatro horas | 1 |

El desempate ordena por importe de descuento descendente, tienda y ticket. La vista operativa muestra hasta **20 por fecha**, con mínimo **2 puntos**. La advertencia de calidad viaja junto al ticket y aporta cero puntos. Los umbrales son decisiones iniciales de diseño. La operación humana conserva la decisión de abrir y cerrar cada caso.

**Ejemplo simulado usado en la prueba.** Un ticket con $40 de descuento sobre $100 tiene una tasa del 40% frente a una media contextual del 10%. Si registra autoaprobación y dura 245 minutos, suma 6 puntos (3 + 2 + 1). Queda primero por score y tercero por importe en ese lote. El modelo también identifica cuándo usa la referencia de cadena o carece de historial.

La base usa movimientos positivos y habilita revisiones con evidencia directa aun cuando la cohorte es pequeña. El benchmark de ranking por importe enfrenta la misma población de candidatos y las mismas plazas diarias. El SQL de evaluación compara sus posiciones durante los últimos 21 días disponibles. La comparación mide cobertura y solapamiento entre listas. El valor predictivo se evaluará con resultados de auditoría humana.

## Primera ejecución en Databricks

- [Corrida histórica, 18 de noviembre](https://dbc-eb170ead-6845.cloud.databricks.com/jobs/1077728338396415/runs/700306622758077?o=7474659154935244). Ingesta, compuerta, resumen histórico y publicación del score en éxito. El destino es el esquema personal de `phase3` en el catálogo `workspace`; se procesaron 115 archivos con 2,142,846 tickets admitidos.
- [Dashboard publicado](https://dbc-eb170ead-6845.cloud.databricks.com/dashboardsv3/01f1e3bc8da91e4d95ee22717db572ee/published?w=7474659154935244). Usa el warehouse del reto con los permisos de datos de quien lo publica.
- El score publicó **268,580 tickets elegibles** para el histórico. En los 21 días evaluados (31 de julio al 20 de agosto), hubo 46,387 candidatos. Usaron referencia local 40,686, referencia de cadena 5,347 y 354 quedaron con historial insuficiente. Cobertura de referencia, **99.24%**.
- Con el mismo presupuesto de 420 casos por lista, los dos rankings coincidieron en **49**. La cola asignó **371** plazas a tickets distintos de los seleccionados por importe. Dentro de la cola, 413 recibieron puntos por una tasa inusual. El piloto debe medir qué casos fueron accionables.

- [Reejecución incremental sin nuevas entradas](https://dbc-eb170ead-6845.cloud.databricks.com/jobs/1077728338396415/runs/1116339657234833?o=7474659154935244). Coincidieron conteos y huellas de Bronze (2,142,846 filas), KPIs (130,259) y modelo (268,580), excluyendo la hora de publicación.
- [Regresión y análisis en Databricks](https://dbc-eb170ead-6845.cloud.databricks.com/jobs/836429566572761/runs/57036081848935?o=7474659154935244). Pasaron las regresiones sintéticas, los controles sobre el histórico y los tres notebooks de análisis.
- [Reproducción con dos archivos sintéticos](https://dbc-eb170ead-6845.cloud.databricks.com/?o=7474659154935244#job/930161027546315/run/212705952639998). Con el mismo checkpoint Auto Loader produjo **1 → 3 → 3** filas en Bronze después de dos llegadas y una reejecución. Dos tickets fueron admitidos. El segundo, con tres advertencias, conservó $10.00 de descuento y propina nula. El tercer registro quedó en cuarentena por llave incompleta.
- Los cuatro datasets del dashboard se ejecutaron en su warehouse sobre el esquema desplegado. El 20 de agosto devuelve **20 tickets** con motivos y referencia. Calidad mostró cero llaves duplicadas y 100% de cobertura de conciliación en el histórico.

## Ingesta, calidad y publicación

- **Entrada.** Auto Loader lee archivos JSON diarios e inmutables en `<source_path>/facts/checks/brand=rmh/dt=AAAA-MM-DD/`. Un archivo nuevo debe tener ruta nueva. La fecha de negocio debe coincidir con la carpeta. El checkpoint conserva el progreso. Las correcciones que reemplazan un ticket necesitan un contrato de revisiones con una versión explícita.
- **Advertencias.** Campos nuevos de raíz o anidados, artículo sin ID con importes válidos y propina ausente entran a Silver con `_dq_warnings`. Un detalle sin ID sigue aportando a importes y volumen de artículos, con esa limitación para análisis de producto. Si falta una propina, el total de propina del ticket queda nulo. Ventas, importes de pago y descuentos utilizables se conservan.
- **Cobertura.** La conciliación usa los tickets con propina observable. El dashboard informa tanto la conciliación como su cobertura. Las sumas de propina agregan únicamente propinas observadas. Calidad muestra conteos de advertencias admitidas, propinas desconocidas y líneas sin identificador.
- **Cuarentena.** El JSON y sus coordenadas permanecen en Bronze. Un error de formato, llave, fecha o importe esencial deja fuera el registro afectado. La compuerta conserva los controles críticos existentes. Un diagnóstico de archivo vacío o ilegible representa un archivo de cardinalidad desconocida. Los datos admisibles continúan a Silver. Si falla la compuerta, la última cola publicada sigue disponible y el pipeline y la cola pueden mostrar distintas marcas de actualización.
- **Ejecución.** `refresh_pipeline → data_quality_gate → publish_review_queue`. El resumen histórico de empleados/tiendas también se ejecuta tras la compuerta. El score recalcula todas las fechas disponibles a partir de tablas actualizadas, de modo que una llegada tardía válida puede modificar los días siguientes de su ventana. Cada publicación reemplaza su tabla en un commit Delta. La hora de publicación cambia al repetir, aunque las posiciones pueden quedar idénticas.
- **Cadencia.** La configuración propone 06:00 `America/Chicago`, una corrida simultánea y reintentos. En QA se ejecuta a demanda. La fecha histórica máxima por sí sola no demuestra frescura. Se propone activar la programación al acordar el horario de entrega del POS y el umbral de atraso con Operaciones.

Referencias de plataforma. [Auto Loader y archivos inmutables](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/faq), [parametrización de dashboards en bundles](https://docs.databricks.com/aws/en/dev-tools/bundles/examples#dashboard-catalog-and-schema-parameterization).

## Dashboard y demo

1. **Descuentos.** KPIs de tickets, bruto, descuento y tasa ponderada `SUM(descuento) / SUM(bruto)`, con barras por forma de pago y canal. Los filtros globales aparecen en el panel lateral.
2. **Cola de revisión.** Elegir un día y leer el motivo de un caso, su tasa y la referencia. La posición es global por fecha. Filtrar una tienda muestra sus tickets dentro de ese top global. Comparar la posición por score con la posición por monto y consultar el desglose de puntos, las desviaciones y las advertencias de calidad.
3. **Calidad y frescura.** Revisar el último día del pipeline, el último día con candidatos, la hora de publicación, propinas no observables y los conteos de advertencias y cuarentena. El dashboard omite JSON original, nombres e IDs de empleados.

El recurso `revision_descuentos` de `phase3` configura `embed_credentials: true`. El dashboard publicado ejecuta consultas con los permisos de datos de quien lo publica. La página de incidencias consulta un agregado de Gold con fecha, archivo, tipo, motivo y conteo. Cada espectador necesita acceso al dashboard. El target `demo` incorpora una cuarta página con casos sembrados, sobre su volumen y esquema dedicados. [Guía y evidencia de la simulación](demo_fase3.md).

## Alcance de la presentación final

| Entregable de la rúbrica | Evidencia prevista |
|---|---|
| Pipeline funcional | Reproducir dos llegadas, reejecutar sin archivo nuevo y comprobar huellas de filas y totales. Medir tiempos de ingesta y ejecución. |
| Calidad y trazabilidad | Demostrar una advertencia que conserva un ticket, una cuarentena y una falla de compuerta, con sus conteos por capa. |
| Insights | Contrastar efectivo, duración y canal. Cuantificar cuánto cambia el top 20 al usar contexto y explicar casos individuales. |
| Dashboard y KPIs | Mostrar las tres páginas, filtros y dos fechas de negocio, incluyendo la trazabilidad de una alerta. |
| Solución analítica | Medir cobertura y comparar con ranking por importe con el mismo presupuesto diario. Usar observaciones estrictamente anteriores para cada score. |
| Recomendaciones | Revisar primero autorizaciones discrecionales y tickets de larga duración. En el piloto, auditar muestras de ambas listas y una muestra fuera de ellas. |
| Documentación técnica | Reproducir el bundle, las pruebas, la definición del score, supuestos, responsables y respuesta ante fallas. |
| Presentación ejecutiva | Contar la decisión, mostrar el recorrido de un ticket y presentar resultados del piloto si las etiquetas están disponibles. |

Para el piloto, etiquetar cada expediente como **accionable**, **legítimo** o **evidencia insuficiente** con un checklist común. Verificar autorización, elegibilidad de promoción, momento de descuento y cierre. Ocultar al revisor el ranking de origen y resolver discrepancias. Reportar casos accionables por cada 20 revisiones, casos sin evidencia, cobertura de referencia, horas de revisión y monto asociado. Sin etiquetas revisadas, reportar cobertura, comparación de listas y casos ilustrativos como evidencia de funcionamiento.

## Archivos modificados y reproducción

| Archivo | Cambio |
|---|---|
| `src/transformations/bronze/bronze_checks.py` | Agrega advertencias recuperables, valida capacidad decimal y mantiene cuarentena y trazabilidad. |
| `src/transformations/silver/st_checks_cleaned.py`, `st_details_cleaned.py` | Conservan advertencias, propina agregada desconocida y líneas sin ID. |
| `src/transformations/gold/mv_calidad_datos.sql`, `mv_incidencias_ingesta.sql` | Añaden cobertura y conteos de calidad, y exponen un agregado de incidentes sin procesar el JSON en el dashboard. |
| `src/jobs/modelo_revision.sql`, `publicar_revision.py` | Calculan el score, explicaciones, ranking por monto y snapshot Delta posterior a calidad. |
| `databricks.yml`, `resources/jobs/*.yml` | Agregan tarea de publicación, opción de pausa y destino aislado `phase3` con recursos propios y job de aceptación. |
| `resources/dashboards/revision_descuentos.lvdash.json` | Tres páginas AI/BI, consultas, filtros y tabla de revisión. |
| `tests/acceptance/validate_pipeline.py`, `replay_ingestion.py`, `validation/sql/fase3_*.sql` | Regresiones de calidad y score, reproducción de dos llegadas, idempotencia y comparación histórica de listas. |
| `scripts/collect_evidence.py` | Permite seleccionar las consultas de Fase 3 por nombre y conserva el alcance predeterminado de Fase 2. |
| `README.md`, `docs/calidad.md`, `docs/fase3*.md` | Enlazan la entrega y explican operación, evidencia y pitch. |

```bash
python3 scripts/validate_local.py
databricks bundle validate -p APPLEBEES -t phase3 --var dashboard_warehouse_id=ID_DEL_WAREHOUSE
databricks bundle plan -p APPLEBEES -t phase3 --var dashboard_warehouse_id=ID_DEL_WAREHOUSE
databricks bundle deploy -p APPLEBEES -t phase3 --var dashboard_warehouse_id=ID_DEL_WAREHOUSE
databricks bundle run daily_orchestration_job -p APPLEBEES -t phase3 --var dashboard_warehouse_id=ID_DEL_WAREHOUSE
databricks bundle run validation_job -p APPLEBEES -t phase3 --var dashboard_warehouse_id=ID_DEL_WAREHOUSE
python3 scripts/collect_evidence.py --warehouse-id ID_DEL_WAREHOUSE --schema ESQUEMA_DEL_TARGET \
  --only fase3_revision.sql --output .local/fase3/benchmark.json
```

Las rutas del dashboard usan el catálogo y esquema del target. Un destino nuevo relee el histórico desde el origen para aplicar el cambio de admisión. En un esquema con checkpoints previos se necesita una migración o una reconstrucción planificada para que filas antiguas también adopten el nuevo tratamiento.

La prueba de llegadas es opcional y puede ejecutarse desde el notebook sincronizado `tests/acceptance/replay_ingestion`, indicando `catalog` y `schema` del target Fase 3. Crea un volumen privado con rutas aleatorias y una tabla de evidencia por corrida. Usa entradas sintéticas y el mismo parser del pipeline.
