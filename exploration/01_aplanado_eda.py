# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Arquitectura y grano de las tablas
# MAGIC Exploración de solo lectura sobre el pipeline desplegado. Ejecutar primero el job del bundle.
# MAGIC Seleccionar el mismo catálogo/esquema del target; no crea ni sobrescribe tablas.
# MAGIC El aplanado productivo está versionado en `src/transformations/silver/`.

# COMMAND ----------
from pyspark.sql import functions as F

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "applebees")
catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
import re
assert all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", x) for x in (catalog, schema))
db = f"{catalog}.{schema}"

# COMMAND ----------
# MAGIC %md
# MAGIC | Tabla | Grano | Uso |
# MAGIC |---|---|---|
# MAGIC | bronze_checks | Ticket o diagnóstico de archivo | JSON original, trazabilidad y recuperación |
# MAGIC | silver_checks | Tienda × fecha × ticket | Importes conciliados y señales del ticket |
# MAGIC | silver_items | Línea de item | Venta atribuida al empleado; modificadores a $0 identificados |
# MAGIC | silver_discounts | Descuento de item o ticket | Aplicación, autorización y categoría |
# MAGIC | silver_payments | Movimiento de pago | Medio de pago y propina; conserva reversos |
# MAGIC | silver_voids | Anulación | Motivo, importe y autorización |
# MAGIC Los detalles repiten la llave del ticket porque su grano es más fino. No se deduplican por esa llave.

# COMMAND ----------
counts = [(name, spark.table(f"{db}.{name}").count()) for name in
          ("bronze_checks", "silver_checks", "silver_items", "silver_discounts", "silver_payments", "silver_voids")]
display(spark.createDataFrame(counts, "tabla string, filas long"))
display(spark.table(f"{db}.gold_calidad_datos"))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Ejemplo de transformación sin datos personales
# MAGIC `descuento = disc_item + disc_check`; `venta_neta = sold - disc_check`.
# MAGIC La propina es `-Gratuity`, sin recortar anomalías a cero. La fuente queda preservada en bronze.

# COMMAND ----------
display(spark.table(f"{db}.silver_checks")
        .select("dt", "LocationId", "CheckId", "gross", "sold", "disc_item", "disc_check", "venta_neta", "tax", "tip", "paid")
        .orderBy("dt", "LocationId", "CheckId").limit(20))
