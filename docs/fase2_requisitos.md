# Fase 2 · Cobertura de la rúbrica

Seguimos la estructura de la plantilla de Sun Holdings: orquestación en `resources/jobs/` y `resources/pipelines/`, y lógica de tablas en `src/transformations/silver/` y `gold/`. Agregamos bronze, pruebas, exploración y documentación.

| Criterio | Qué hicimos | Dónde verlo |
|---|---|---|
| GitHub Repository & Documentation | Código, notebooks, configuración e instrucciones para ejecutar y recuperar | README, `docs/`, `.github/workflows/validate.yml` |
| Job & Pipeline Design | Job de tres tareas con dependencias, horario diario, reintentos, una corrida a la vez y Repair run | `resources/`, [operación](operacion.md) |
| Transformations & Table Value | Limpieza, aplanado, importes, enriquecimiento y agregación, con grano y propósito de cada tabla | `src/transformations/`, [diccionario](diccionario.md) |
| Streaming, MVs, Liquid Clustering & Expectations | Auto Loader y streaming tables, materialized views en gold, clustering por fecha/tienda/empleado, expectations por tabla | Código, [operación](operacion.md), `validation/sql/clustering.sql` |
| Data Quality Checks | Tipos, nulos, campos nuevos, duplicados, completitud entre capas, referencias y conciliación | [Calidad](calidad.md), `tests/`, compuerta del job |
| Analysis, Insights & Business Value | Hallazgos con denominadores claros, motor de riesgo y tiendas a priorizar | [Validación](validacion.md), `exploration/03_eda_descuentos.py` |
