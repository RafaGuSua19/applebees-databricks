# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Análisis reproducible y prioridades de negocio
# MAGIC Solo lectura sobre tablas del bundle. Los resultados son señales para revisión, no prueba de fraude.
# MAGIC Elegir el catálogo/esquema validado. Cada `display` permite añadir una visualización en Databricks.

# COMMAND ----------
from pyspark.sql import functions as F
import re

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "applebees")
parts = [dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")]
assert all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", x) for x in parts)
db = ".".join(parts)
kpi = spark.table(f"{db}.gold_kpis_diarios")
ck = spark.table(f"{db}.silver_checks")
ds = spark.table(f"{db}.silver_discounts")
emp = spark.table(f"{db}.gold_riesgo_empleados")

# COMMAND ----------
# MAGIC %md ## 1. Panorama general y tendencia diaria

# COMMAND ----------
display(kpi.agg(F.sum("tickets").alias("tickets"), F.sum("venta_bruta").alias("venta_bruta"),
                F.sum("descuento").alias("descuento"),
                F.expr("try_divide(sum(descuento),sum(venta_bruta))").alias("pct_desc")))
display(kpi.groupBy("dt").agg(F.sum("venta_bruta").alias("venta_bruta"), F.sum("descuento").alias("descuento"),
    F.expr("try_divide(sum(descuento),sum(venta_bruta))").alias("pct_desc")).orderBy("dt"))

# COMMAND ----------
# MAGIC %md ## 2. Medio de pago y canal
# MAGIC Comparar tasas ponderadas por venta; no promediar porcentajes de grupos de distinto tamaño.

# COMMAND ----------
for dimension in ("tipo_pago", "Canal"):
    display(kpi.groupBy(dimension).agg(F.sum("tickets").alias("tickets"),
        F.sum("venta_bruta").alias("venta_bruta"), F.sum("descuento").alias("descuento"),
        F.expr("try_divide(sum(descuento),sum(venta_bruta))").alias("pct_desc")).orderBy(F.desc("descuento")))

# COMMAND ----------
# MAGIC %md ## 3. Tickets abiertos cuatro horas y descuentos completos

# COMMAND ----------
display(ck.groupBy("abierto_4h").agg(F.count("*").alias("tickets"),
    F.sum("descuento").alias("descuento"), F.expr("try_divide(sum(descuento),sum(gross))").alias("pct_desc")))
display(ck.agg(F.sum(F.when(F.col("cien_pct_desc"), F.col("descuento"))).alias("descuento_tickets_100pct"),
              F.sum("descuento").alias("descuento_total")))

# COMMAND ----------
# MAGIC %md ## 4. Score explicable y población
# MAGIC Grano: empleado × tienda. Solo IDs positivos en catálogo, con al menos 100 líneas de precio positivo.
# MAGIC Comparación contra mediana de empleados elegibles en la misma tienda. Si la mediana es cero,
# MAGIC el cociente queda nulo y esa regla no suma puntos; se revisa antes de calibrar el modelo.

# COMMAND ----------
display(emp.groupBy("nivel_riesgo").agg(F.count("*").alias("pares_empleado_tienda"),
                                      F.sum("desc_emp").alias("descuento_asociado")))
display(spark.table(f"{db}.gold_riesgo_tiendas")
        .orderBy(F.desc("empleados_riesgo_alto"), F.desc("pct_desc")).limit(15))
display(ds.filter("Amount > 0 AND autoaprobado").agg(
    F.countDistinct("EmployeeId").alias("ids_positivos_en_todos_los_descuentos"),
    F.countDistinct(F.struct("LocationId", "EmployeeId")).alias("pares_empleado_tienda")))
display(emp.filter("n_autoaprobados > 0").agg(F.count("*").alias("pares_autoaprobados_en_poblacion_evaluada")))

# COMMAND ----------
# MAGIC %md ## Conclusiones y decisiones
# MAGIC El efectivo concentra una proporción del descuento mayor que su participación en ventas.
# MAGIC To Go y tickets abiertos cuatro horas o más justifican revisar procesos de autorización y cierre.
# MAGIC El score permite priorizar expedientes con varias señales; debe contrastarse con tickets,
# MAGIC promociones y autorizaciones antes de actuar. Los descuentos asociados no equivalen a pérdida
# MAGIC recuperable. Calibrar con prevención de pérdidas y medir precisión de las revisiones confirmadas.
# MAGIC Los valores, denominadores y evidencia de ejecución están en el README y `docs/validacion.md`.
