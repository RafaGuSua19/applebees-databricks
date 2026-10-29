# Fase 2 · Presentación del pipeline (requisitos de Sun Holdings)

Presentación: jueves 29 oct 2026, 3:50–3:55 PM Central (≈ 2:50 PM Guadalajara). Exactamente 5 minutos.
Antes de presentar: enviar la URL del repositorio por el formulario (obligatorio).

## Entregables
- Repositorio GitHub completo y organizado (notebooks, código, documentación, configuración, instrucciones).
- Job de Databricks: programación o disparo, dependencias entre tareas, manejo de fallas y reprocesos.
- Arquitectura: cómo fluyen los datos de la fuente a las tablas finales.
- Transformaciones y tablas: limpieza, preparación, enriquecimiento, agregación; propósito y valor de cada tabla.
- Calidad de datos: nulos, duplicados, registros inválidos, formatos inconsistentes, etc.
- Buenas prácticas: streaming, materialized views, liquid clustering, expectations.
- Análisis y valor de negocio a partir de las tablas finales.

## Estructura sugerida de la presentación
1. Objetivo de negocio · 2. Datos fuente y arquitectura · 3. Transformaciones · 4. Calidad de datos · 5. Análisis final · 6. Conclusión.

## Rúbrica (1 a 4 cada criterio)
- GitHub Repository & Documentation
- Job & Pipeline Design
- Transformations & Table Value
- Streaming, Materialized Views, Liquid Clustering & Expectations
- Data Quality Checks
- Analysis, Insights & Business Value
- Technical Communication

## Estructura de repo obligatoria (plantilla)
resources/jobs/daily_orchestration_job.yml · resources/pipelines/lakeflow_pipeline.yml ·
src/transformations/silver/ (st_*.py, mv_*.sql) · src/transformations/gold/ (st_*.py, mv_*.sql)
