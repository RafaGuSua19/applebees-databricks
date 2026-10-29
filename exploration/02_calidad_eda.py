# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Calidad y excepciones
# MAGIC Solo lectura. Las reglas de publicación están en `src/jobs/quality_rules.py`.
# MAGIC Errores estructurales se conservan en bronze y bloquean alertas. Excepciones de negocio se miden
# MAGIC y conservan para revisión humana; eliminar automáticamente pagos negativos alteraría los totales.

# COMMAND ----------
from pyspark.sql import functions as F
import re

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "applebees")
parts = [dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")]
assert all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", x) for x in parts)
db = ".".join(parts)
ck = spark.table(f"{db}.silver_checks")

# COMMAND ----------
# MAGIC %md ## Completitud, unicidad, referencias y consistencia por día

# COMMAND ----------
display(spark.table(f"{db}.gold_calidad_datos"))
display(ck.groupBy("dt").agg(F.count("*").alias("tickets"),
    F.avg((F.abs(F.col("paid") - (F.col("sold") - F.col("disc_check") + F.col("tax") + F.col("tip"))) <= 0.05)
          .cast("double")).alias("pct_conciliados")).orderBy("dt"))
display(ck.select([F.sum(F.col(c).isNull().cast("int")).alias(c) for c in ck.columns]))
display(spark.table(f"{db}.bronze_checks").groupBy("_rescued_data").count())

# COMMAND ----------
# MAGIC %md ## Excepciones con política explícita
# MAGIC - Tickets sin items pueden representar cancelaciones: se conservan y cuentan.
# MAGIC - `gross - sold = disc_item` y `paid = sold - disc_check + tax + tip` usan tolerancia de $0.05.
# MAGIC - Importes negativos y descuentos mayores al bruto quedan visibles; no se reescribe la fuente.
# MAGIC - ID cero no identifica a una persona: nunca es autoaprobación y no entra al score.
# MAGIC - Campos nuevos o tipos incompatibles requieren revisar el contrato y reprocesar desde el origen.

# COMMAND ----------
display(spark.table(f"{db}.silver_payments").filter("Amount < 0")
        .groupBy("PayCatName").agg(F.count("*").alias("movimientos"), F.sum("Amount").alias("monto")))
display(ck.agg(
    F.count_if(F.expr("n_items = 0")).alias("sin_items"),
    F.count_if(F.expr("abs(gross - sold - disc_item) > 0.05")).alias("descuadre_item"),
    F.count_if(F.expr("descuento > gross + 0.05")).alias("exceso_descuento")))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Decisiones confirmadas
# MAGIC `GrossPrice` representa la línea completa: no se multiplica otra vez por cantidad.
# MAGIC Los descuentos de item y ticket son independientes y se suman. `PayCatName`, normalizado,
# MAGIC identifica efectivo; `IsCashDebit` no sirve para ese propósito. Los montos de silver usan
# MAGIC DECIMAL(18,2). Los resultados vigentes y los límites del control están en `docs/validacion.md`.
