# Despliegue, operación y recuperación

## Requisitos y acceso

- Databricks CLI autenticada (`databricks auth profiles`; en la validación se usó `APPLEBEES`).
- Workspace con Unity Catalog, Lakeflow Spark Declarative Pipelines y cómputo serverless habilitados.
- `USE CATALOG`, `CREATE SCHEMA` en el catálogo de destino; `USE SCHEMA`, `CREATE TABLE` y permisos para materialized views/streaming tables en el esquema; acceso para crear/ejecutar jobs y pipelines.
- `USE CATALOG`, `USE SCHEMA` y `READ VOLUME` en el volumen de origen.
- Python 3.11+ para las verificaciones locales. No requiere instalar Spark ni credenciales para esas pruebas.

El volumen debe contener `facts/checks/brand=rmh/dt=AAAA-MM-DD/*.json` y `dimensions/*/{locations,revenueCenters,employees,items}.json`. Cada archivo de tickets contiene un arreglo JSON. La entrega de referencia contiene 115 archivos diarios más cuatro catálogos. No subir datos, tokens ni resultados individuales a GitHub.

## Validación y despliegue independiente

```bash
python3 scripts/validate_local.py
databricks bundle validate -t qa -p APPLEBEES
databricks bundle plan -t qa -p APPLEBEES
databricks bundle deploy -t qa -p APPLEBEES
databricks bundle run daily_orchestration_job -t qa -p APPLEBEES
databricks bundle run validation_job -t qa -p APPLEBEES
# Repetir sin nuevos archivos: debe conservar los conteos y los importes.
databricks bundle run daily_orchestration_job -t qa -p APPLEBEES
```

`dev` es el target por defecto. Cada target publica en `workspace.applebees_<target>_<usuario>`, por ejemplo `workspace.applebees_qa_a01706880`. El estado y los checkpoints se mantienen por usuario/target. `qa` añade un job de pruebas que ejecuta las transformaciones productivas con datos sintéticos, verifica los totales del dataset de la competencia y ejecuta los tres notebooks de exploración. Sus comprobaciones de volumen exacto se deben actualizar deliberadamente cuando se amplíe ese dataset.

Variables: `catalog`, `schema`, `source_path` y `failure_emails`. Ejemplo de instancia independiente:

```bash
databricks bundle validate -t dev -p APPLEBEES \
  --var 'catalog=workspace,schema=applebees_dev_personal,source_path=/Volumes/workspace/default/applebees'
```

Usar los mismos valores en `validate`, `plan`, `deploy` y `run`. Para valores persistentes, crear `.databricks/bundle/<target>/variable-overrides.json` (ignorado por Git). Las notificaciones están vacías durante QA; configurar `failure_emails` con destinatarios autorizados para la operación compartida. El job registra errores aunque no haya correo configurado.

## Actualizar la instancia compartida existente

El esquema histórico `workspace.applebees` pertenece al pipeline original. Un push a GitHub **no despliega** automáticamente el bundle ni actualiza ese esquema. No apuntar un nuevo pipeline a tablas que ya administra otro.

La ruta recomendada es que el responsable del despliegue original use su mismo perfil, target y estado del bundle, con `--var schema=applebees`. Primero revisar `bundle plan`: debe actualizar el pipeline y job existentes, no crear otro pipeline para esas tablas. Si se cambia de responsable, acordar la transferencia y usar `bundle deployment bind` para ambos recursos; vincular no sustituye los permisos, ni evita conflictos con el estado del responsable anterior.

Esta versión cambia el contrato de bronze y los tipos monetarios de silver. La primera actualización de una instancia previa requiere **full refresh** para aplicar la lógica a los 115 días. Validar antes en QA, conservar los archivos fuente y programar una ventana sin lectores de resultados parcialmente reconstruidos:

```bash
# Solo con el estado correcto de la instancia compartida y su responsable:
databricks bundle deploy -t dev -p PERFIL_RESPONSABLE --var schema=applebees
databricks bundle run applebees_pipeline -t dev -p PERFIL_RESPONSABLE \
  --var schema=applebees --full-refresh-all
databricks bundle run daily_orchestration_job -t dev -p PERFIL_RESPONSABLE --var schema=applebees
```

El full refresh reinicia las tablas y checkpoints de ese pipeline: requiere que todas las fuentes históricas sigan disponibles. La validación de esta entrega se hizo en un esquema aislado y deja intacta la instancia histórica.

## Programación y fallos

Flujo: `refresh_pipeline → data_quality_gate → risk_alerts`, con dependencias `ALL_SUCCESS`. Una sola ejecución concurrente. Programación a las 06:00 `America/Chicago`, pausada en ambos targets de desarrollo. Una ejecución manual cumple el disparo necesario para esta entrega. Activar una programación operativa exige decidir el destino compartido, responsable y destinatarios de fallos.

- **Error transitorio del pipeline:** hasta dos reintentos, separados por cinco minutos.
- **Error de contrato o calidad:** revisar `_rescued_data` y `_source_file` en bronze y `gold_calidad_datos`. La compuerta no reintenta ni ejecuta alertas sobre métricas incompletas. Un fallo no revierte automáticamente las tablas ya materializadas; los consumidores deben usar la última corrida completa aprobada.
- **Error en alertas:** un reintento tras un minuto. El notebook muestra prioridades en la salida del job; no envía tickets, correos de riesgo ni notificaciones de negocio.
- **Repair run:** tras corregir una causa transitoria, reparar las tareas fallidas. Si cambió la transformación, refrescar primero el pipeline y volver a ejecutar la compuerta; reparar solo la compuerta no recalcula datos.
- **Cambio de lógica sobre histórico o corrección de un archivo procesado:** no editar silenciosamente un archivo ya consumido. Auto Loader está diseñado aquí para archivos nuevos e inmutables. Corregir la fuente de manera controlada y ejecutar full refresh del destino afectado. No usar `skipChangeCommits` para ocultar cambios.
- **Rollback:** recuperar la versión de Git previamente validada, desplegar con el mismo estado y reconstruir desde las fuentes si cambió el esquema. No basta revertir el commit para revertir tablas.

## Permisos y datos personales

Bronze conserva catálogos con datos personales y JSON de origen: acceso solo al equipo de ingeniería autorizado. Silver de empleados excluye `Name`, `DateOfBirth` e `IsMinor`; gold utiliza IDs y agregados. Esto reduce exposición, pero los IDs siguen siendo identificadores seudonimizados. Unity Catalog permite aplicar permisos por esquema/tabla; la separación bronze/silver/gold por nombre no es por sí misma una frontera de acceso. Otorgar a consumidores solo las tablas necesarias y revisar grants antes de compartir fuera del equipo.

## Técnicas y costo

Auto Loader y silver son incrementales mediante checkpoints. Las vistas materializadas las mantiene Databricks; su técnica puede ser incremental o recálculo completo según el plan y el costo. Los catálogos JSON y el score con mediana/comparación global pueden requerir recálculo completo. Consultar los eventos `planning_information` del pipeline para confirmar la técnica de cada corrida.

Liquid clustering usa fecha/tienda y empleado en descuentos según los filtros esperados. No hay particionado fijo. `maxFilesPerTrigger=1` limita presión de memoria de archivos diarios grandes; no garantiza un límite de bytes si cambian sus tamaños. Modo triggered porque la entrada es diaria. El JSON por ticket en bronze aumenta almacenamiento para permitir auditoría y recuperación; evita interpretar de nuevo un arreglo tipado completo de 70–90 MB en memoria.

Referencias oficiales: [variables del bundle](https://docs.databricks.com/aws/en/dev-tools/bundles/variables), [comportamiento de from_json](https://docs.databricks.com/aws/en/sql/language-manual/functions/from_json), [refresco de vistas materializadas](https://docs.databricks.com/aws/en/ldp/incremental-refresh/).

## Reproducir la prueba de idempotencia

Con una versión ya desplegada y sin añadir archivos entre ambos snapshots:

```bash
python3 scripts/collect_evidence.py --warehouse-id ID_DEL_WAREHOUSE --schema ESQUEMA_DEL_TARGET \
  --only idempotencia.sql --output .local/validation/before.json
databricks bundle run daily_orchestration_job -t qa -p APPLEBEES
python3 scripts/collect_evidence.py --warehouse-id ID_DEL_WAREHOUSE --schema ESQUEMA_DEL_TARGET \
  --only idempotencia.sql --output .local/validation/after.json
python3 scripts/compare_evidence.py .local/validation/before.json .local/validation/after.json
```

No comparar huellas de versiones distintas del código: un cambio intencional de lógica o tipo puede cambiar el contenido. Se excluye `gold_calidad_datos` de la huella porque `calculado_en` cambia deliberadamente en cada corrida.
