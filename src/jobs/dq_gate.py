# Databricks notebook source
# Una fila válida de métricas es requisito para emitir alertas.
from quality_rules import qualified_schema, quality_errors

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "applebees")
ESQUEMA = qualified_schema(dbutils.widgets.get("catalog"), dbutils.widgets.get("schema"))
rows = [row.asDict() for row in spark.table(f"{ESQUEMA}.gold_calidad_datos").limit(2).collect()]
for row in rows:
    for key, value in row.items():
        print(f"{key}: {value}")
errores = quality_errors(rows)
if errores:
    raise ValueError("Falló la compuerta de calidad: " + "; ".join(errores))
print("Calidad OK: el job continúa.")
