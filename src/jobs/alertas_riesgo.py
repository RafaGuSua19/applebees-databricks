# Databricks notebook source
# Alertas de riesgo para operaciones: empleados y tiendas a revisar.
from pyspark.sql import functions as F

ESQUEMA = "workspace.applebees"

emp = spark.table(f"{ESQUEMA}.gold_riesgo_empleados")
print("Empleados por nivel de riesgo:")
display(emp.groupBy("nivel_riesgo").count().orderBy("nivel_riesgo"))

display(emp.filter("nivel_riesgo = 'Alto'")
           .select("LocationId", "EmployeeId", "score_riesgo", F.round("veces_vs_tienda", 2).alias("veces_vs_tienda"),
                   F.round("pct_efectivo", 2).alias("pct_efectivo"), "n_sin_gerente", "n_autoaprobados",
                   "tickets_4h_con_desc", F.round("desc_emp", 0).alias("descuento"))
           .orderBy(F.desc("score_riesgo"), F.desc("descuento")))

display(spark.table(f"{ESQUEMA}.gold_riesgo_tiendas")
             .orderBy(F.desc("empleados_riesgo_alto"), F.desc("pct_desc")).limit(15))
