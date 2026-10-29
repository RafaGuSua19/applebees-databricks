# Cobertura de los documentos de Fase 2

Fuentes: *Basic Databricks GitHub Repository Template – SH Shared Services & BI*, páginas 1–2, y *Phase 2: Pipeline Presentation*, entregables de página 2 y rúbrica de páginas 3–5. Los PDF se usan como criterios de evaluación, no como instrucciones para iniciar sesión, enviar formularios o preparar la presentación oral.

La plantilla exige separar `resources/jobs/`, `resources/pipelines/` y lógica de tablas en `src/transformations/silver/` y `gold/`. Esta estructura se conserva; bronze, pruebas, exploración y documentación la complementan. Los nombres de tablas mostrados en la plantilla son ejemplos, no entidades obligatorias del proyecto.

| Criterio visible | Cobertura en el repositorio | Evidencia para revisión |
|---|---|---|
| GitHub Repository & Documentation | Código, notebooks, configuración, requisitos, ejecución, recuperación y fuentes de evidencia organizados | README, `docs/`, `scripts/`, `.github/workflows/validate.yml` |
| Job & Pipeline Design | Flujo completo de tres tareas, dependencias, disparo manual/diario, reintentos, concurrencia y reproceso | YAML de recursos, diagrama, `docs/operacion.md` y corridas en `docs/validacion.md` |
| Transformations & Table Value | Limpieza, aplanado, importes, enriquecimiento y agregación explicados por grano y propósito | `src/transformations/`, `docs/diccionario.md`, notebooks 01/03 |
| Streaming, Materialized Views, Liquid Clustering & Expectations | Uso implementado y justificación de incrementalidad, recálculo, clustering y reglas declarativas | Código, eventos de ejecución, `docs/operacion.md` y validación de clustering |
| Data Quality Checks | Estructura/tipos, nulos, campos nuevos, duplicados, completitud, referencias, consistencia, precisión y excepciones | `docs/calidad.md`, pruebas unitarias/Spark, consultas y compuerta real |
| Analysis, Insights & Business Value | Métricas verificables, denominadores explícitos, prioridades, límites y recomendaciones de calibración | `docs/validacion.md`, consultas de negocio y notebook 03 |

Los siete entregables de la página 2 quedan representados en estas seis filas: repositorio, job, arquitectura, transformaciones/tablas, calidad, buenas prácticas y análisis. La preparación del material y la ejecución de la presentación oral se harán por separado cuando se soliciten. Este repositorio no garantiza una calificación: la evaluación también depende de su accesibilidad para los evaluadores y de la exposición del equipo.

La página 6 del PDF adjunto no contiene una fila legible de evaluación. No se inventa un criterio adicional ni un horario de presentación que no está en los documentos. El acceso externo a GitHub y el envío de la URL requieren comprobación por el equipo al entregar.
