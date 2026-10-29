# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Aplanado (capa Silver)
# MAGIC **Objetivo:** convertir los checks anidados (`bronze_checks`) en tablas planas para el análisis.
# MAGIC
# MAGIC | Tabla | Grano (una fila por…) |
# MAGIC |---|---|
# MAGIC | `silver_items` | item vendido |
# MAGIC | `silver_discounts` | descuento aplicado (nivel check o nivel item, columna `Nivel`) |
# MAGIC | `silver_payments` | pago (con `Tip` = −`Gratuity`, porque el sistema guarda la propina en negativo) |
# MAGIC | `silver_voids` | void |
# MAGIC | `silver_tax` | impuesto |
# MAGIC | `silver_checks` | ticket, con totales agregados |
# MAGIC
# MAGIC Llave de un ticket: `LocationId + dt + CheckId`. **Correr una sola vez.**

# COMMAND ----------

from pyspark.sql import functions as F

c = (spark.table("workspace.default.bronze_checks")
     .withColumnRenamed("Id", "CheckId")
     .withColumnRenamed("RevenueCenterId", "CheckRevenueCenterId"))

keys = ["CheckId", "LocationId", "CheckRevenueCenterId", "dt", "OpenTime",
        "CloseTime", "TableName", "TrafficCount", "LoyaltyId"]

def guardar(df, nombre):
    df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"workspace.default.{nombre}")
    print(nombre, spark.table(f"workspace.default.{nombre}").count())

# COMMAND ----------

# Items vendidos
items = (c.select(*keys, F.explode("ItemsSold").alias("i"))
          .select(*keys, "i.*").drop("Discounts"))
guardar(items, "silver_items")

# Descuentos: nivel check + nivel item en una sola tabla
disc_check = (c.select(*keys, F.explode("Discounts").alias("d"))
               .select(*keys, "d.*").withColumn("Nivel", F.lit("check")))
disc_item = (c.select(*keys, F.explode("ItemsSold").alias("i"))
              .select(*keys, F.col("i.ItemId"), F.col("i.ItemName"),
                      F.col("i.Sequence").alias("ItemSequence"),
                      F.col("i.EmployeeId").alias("ItemEmployeeId"),
                      F.explode("i.Discounts").alias("d"))
              .select(*keys, "ItemId", "ItemName", "ItemSequence", "ItemEmployeeId", "d.*")
              .withColumn("Nivel", F.lit("item")))
guardar(disc_check.unionByName(disc_item, allowMissingColumns=True), "silver_discounts")

# Pagos (Gratuity viene negativa por diseño del sistema -> Tip positiva)
pay = (c.select(*keys, F.explode("Payments").alias("p")).select(*keys, "p.*")
        .withColumn("Tip", -F.col("Gratuity")))
guardar(pay, "silver_payments")

# Voids e impuestos
guardar(c.select(*keys, F.explode("Voids").alias("v")).select(*keys, "v.*"), "silver_voids")
guardar(c.select(*keys, F.explode("Tax").alias("t")).select(*keys, "t.*"), "silver_tax")

# COMMAND ----------

def suma(arr, campo):
    return F.expr(f"coalesce(aggregate({arr}, 0D, (acc, x) -> acc + coalesce(x.{campo}, 0D)), 0D)")

checks = c.select(*keys, "ServiceCharge",
    F.when(F.col("ItemsSold").isNull(), 0).otherwise(F.size("ItemsSold")).alias("n_items"),
    suma("ItemsSold", "GrossPrice").alias("gross"),
    suma("ItemsSold", "SoldPrice").alias("sold"),
    suma("Discounts", "Amount").alias("disc_check"),
    F.expr("""coalesce(aggregate(ItemsSold, 0D, (acc, x) -> acc +
              coalesce(aggregate(x.Discounts, 0D, (a, d) -> a + coalesce(d.Amount, 0D)), 0D)), 0D)""").alias("disc_item"),
    suma("Voids", "Amount").alias("voids"),
    suma("Tax", "Amount").alias("tax"),
    suma("Payments", "Amount").alias("paid"),
    (-suma("Payments", "Gratuity")).alias("tip"),
    F.expr("exists(Payments, p -> p.IsCashDebit)").alias("has_cash_debit"))
guardar(checks, "silver_checks")
