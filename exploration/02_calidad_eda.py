# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Calidad de datos (Data Cleaning & Preparation)
# MAGIC **Objetivo:** documentar volumen, duplicados, nulos, signos, conciliación de montos, outliers y formatos.
# MAGIC Cada sección termina con una celda de **Hallazgos** que hay que llenar: de ahí sale la slide de limpieza.

# COMMAND ----------

from pyspark.sql import functions as F

db = "workspace.default"
ck = spark.table(f"{db}.silver_checks")
it = spark.table(f"{db}.silver_items")
K = ["LocationId", "dt", "CheckId"]

# COMMAND ----------

# MAGIC %md ## 1. Volumen, rango de fechas y unicidad de la llave

# COMMAND ----------

display(ck.agg(
    F.count("*").alias("checks"),
    F.countDistinct(*K).alias("checks_unicos_llave"),
    F.countDistinct("CheckId").alias("checkid_unicos"),
    F.min("dt").alias("fecha_min"), F.max("dt").alias("fecha_max"),
    F.countDistinct("dt").alias("dias"),
    F.countDistinct("LocationId").alias("tiendas")))

dups = ck.groupBy(*K).count().filter("count > 1")
print("llaves duplicadas:", dups.count())
display(dups.limit(20))

# COMMAND ----------

# MAGIC %md
# MAGIC **Hallazgos:**
# MAGIC - …

# COMMAND ----------

# MAGIC %md ## 2. Nulos por columna (silver_checks)

# COMMAND ----------

display(ck.select([F.sum(F.col(c).isNull().cast("int")).alias(c) for c in ck.columns]))

# COMMAND ----------

# MAGIC %md ## 3. Signos de los montos (¿qué viene en negativo además de la propina?)

# COMMAND ----------

revisar = [("silver_discounts", "Amount"), ("silver_voids", "Amount"),
           ("silver_payments", "Gratuity"), ("silver_payments", "Amount"),
           ("silver_items", "GrossPrice"), ("silver_items", "SoldPrice"),
           ("silver_tax", "Amount")]
for t, col in revisar:
    r = (spark.table(f"{db}.{t}")
         .agg(F.min(col).alias("min"), F.max(col).alias("max"),
              F.sum((F.col(col) < 0).cast("int")).alias("negativos"),
              F.sum((F.col(col) > 0).cast("int")).alias("positivos"),
              F.count("*").alias("filas"))
         .collect()[0].asDict())
    print(f"{t}.{col}: {r}")

# COMMAND ----------

# MAGIC %md ## 4. ¿GrossPrice ya incluye la cantidad? (items con Quantity ≠ 1)

# COMMAND ----------

display(it.filter("Quantity != 1")
          .select("ItemName", "Quantity", "GrossPrice", "SoldPrice").limit(20))

# COMMAND ----------

# MAGIC %md ## 5. Conciliación: ¿cuadran los montos del ticket?
# MAGIC Esperado (a validar): `gross − descuentos ≈ sold` y `sold + tax ≈ paid` (± propina/service charge).

# COMMAND ----------

rec = (ck.withColumn("dif_bruto_vs_neto", F.round(F.col("gross") - F.col("sold"), 2))
         .withColumn("dif_pago", F.round(F.col("paid") - (F.col("sold") + F.col("tax")), 2)))
display(rec.select("dif_bruto_vs_neto", "disc_item", "disc_check", "dif_pago", "tip").summary())
display(rec.select(*K, "gross", "sold", "disc_item", "disc_check", "tax", "paid", "tip", "voids")
           .filter("disc_item != 0 OR disc_check != 0").limit(20))

# COMMAND ----------

# MAGIC %md ## 6. ¿Doble conteo de descuentos entre nivel check y nivel item?

# COMMAND ----------

display(ck.agg(
    F.sum(((F.col("disc_check") != 0) & (F.col("disc_item") != 0)).cast("int")).alias("checks_con_ambos"),
    F.sum(((F.col("disc_check") != 0) & (F.col("disc_item") == 0)).cast("int")).alias("solo_nivel_check"),
    F.sum(((F.col("disc_check") == 0) & (F.col("disc_item") != 0)).cast("int")).alias("solo_nivel_item"),
    F.sum(((F.col("disc_check") != 0) &
           (F.round("disc_check", 2) == F.round("disc_item", 2))).cast("int")).alias("montos_identicos")))

# COMMAND ----------

# MAGIC %md
# MAGIC **Decisión:** si `montos_identicos` ≈ `checks_con_ambos`, los descuentos de check repiten los de item → usar solo un nivel en `03_eda` (`USAR_NIVEL`).

# COMMAND ----------

# MAGIC %md ## 7. Tickets atípicos y outliers

# COMMAND ----------

display(ck.agg(
    F.sum((F.col("n_items") == 0).cast("int")).alias("sin_items"),
    F.sum((F.col("paid") == 0).cast("int")).alias("sin_pago"),
    F.sum((F.col("sold") < 0).cast("int")).alias("venta_negativa"),
    F.sum((F.col("TrafficCount") <= 0).cast("int")).alias("sin_comensales")))

display(ck.select(*[F.expr(f"percentile_approx({c}, array(0.01, 0.25, 0.5, 0.75, 0.99))").alias(c)
                    for c in ["gross", "sold", "tip", "n_items", "TrafficCount"]]))

# COMMAND ----------

# MAGIC %md ## 8. Formato de fechas/horas

# COMMAND ----------

display(ck.select("OpenTime", "CloseTime").limit(5))
display(ck.select(F.sum(F.expr("try_to_timestamp(OpenTime)").isNull().cast("int")).alias("OpenTime_no_parsea")))

# COMMAND ----------

# MAGIC %md ## 9. Tablas de dimensiones

# COMMAND ----------

for t in ["bronze_employees", "bronze_items", "bronze_locations", "bronze_revenue_centers"]:
    df = spark.table(f"{db}.{t}")
    print(t, df.count(), "filas | columnas:", df.columns)
    display(df.limit(5))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Resumen de limpieza (para la slide)
# MAGIC - Propina (`Gratuity`) en negativo por diseño → convertida a `Tip` positiva.
# MAGIC - …
