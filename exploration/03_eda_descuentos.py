# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · EDA de descuentos — ¿dónde podría haber abuso?
# MAGIC **Pregunta de negocio:** ¿cuánto dinero se va en descuentos y qué patrones sugieren abuso por parte de empleados?
# MAGIC
# MAGIC **Supuestos validados en `02_calidad`:**
# MAGIC - Llave del ticket = `LocationId + dt + CheckId` (CheckId se reinicia por tienda/día). 0 duplicados.
# MAGIC - `GrossPrice` ya es el total de la línea (incluye cantidad).
# MAGIC - Descuentos de item ya están restados en `SoldPrice` (`gross − sold = disc_item` exacto).
# MAGIC - Descuentos de check se restan después: `paid = sold − disc_check + tax + tip`. **No hay doble conteo** → descuento total = `disc_item + disc_check`.
# MAGIC - 32% de los registros de descuento y 55% de los voids tienen monto $0 → se analizan aparte.
# MAGIC - 67% de las líneas de item cuestan $0 (modificadores: salsas, cubiertos, "ADDS") → para volumen se usan solo líneas con precio > 0.
# MAGIC - **Privacidad:** nunca se muestran `Name` ni `DateOfBirth` de empleados; solo IDs.
# MAGIC
# MAGIC En cada `display()` usa **+ → Visualization** para graficar; ponle título y ejes.

# COMMAND ----------

from pyspark.sql import functions as F

db = "workspace.default"
K = ["LocationId", "dt", "CheckId"]
ck = spark.table(f"{db}.silver_checks")
it = spark.table(f"{db}.silver_items")
ds = spark.table(f"{db}.silver_discounts")
py = spark.table(f"{db}.silver_payments")
vd = spark.table(f"{db}.silver_voids")
loc = spark.table(f"{db}.bronze_locations").select(F.col("Id").alias("LocationId"), F.col("Name").alias("Tienda"))
rc  = spark.table(f"{db}.bronze_revenue_centers").select(F.col("Id").alias("CheckRevenueCenterId"), F.col("Name").alias("Canal"))

def div(a, b):
    """División segura (evita error por división entre cero)."""
    return F.expr(f"try_divide({a}, {b})")

ck = (ck.withColumn("desc", F.col("disc_item") + F.col("disc_check"))
        .withColumn("tiene_desc", F.col("desc") > 0)
        .withColumn("venta_neta", F.col("sold") - F.col("disc_check"))
        .withColumn("tip", F.greatest(F.col("tip"), F.lit(0.0))))   # 3 propinas con signo invertido -> 0
ds_m = ds.filter("Amount > 0")   # descuentos con monto

# Tipo de pago por ticket (IsCashDebit NO marca el efectivo: se usa PayCatName = CASH)
tipo = (py.groupBy(*K).agg(
            F.max((F.upper("PayCatName") == "CASH").cast("int")).alias("cash"),
            F.max(F.col("IsCreditCard").cast("int")).alias("card"),
            F.max(F.col("IsGiftCard").cast("int")).alias("gift"),
            F.max(F.upper("PayCatName").isin("DOORDASH", "UBEREATS", "GRUBHUB", "POSTMATES",
                                             "DELIVERLOGIC", "BITESQUAD", "EZCATER", "FOODJA").cast("int")).alias("app"))
          .withColumn("tipo_pago",
              F.when(F.col("app") == 1, "App delivery")
               .when((F.col("cash") == 1) & (F.col("card") == 0), "Efectivo")
               .when((F.col("card") == 1) & (F.col("cash") == 0), "Tarjeta crédito")
               .when((F.col("card") == 1) & (F.col("cash") == 1), "Mixto")
               .when(F.col("gift") == 1, "Gift card")
               .otherwise("Otro")))
ckp = ck.join(tipo.select(*K, "tipo_pago"), K, "left").fillna("Sin pago", ["tipo_pago"])

# COMMAND ----------

# MAGIC %md ## 1. Panorama general (KPIs para la slide de contexto)

# COMMAND ----------

kpi = (ck.agg(F.countDistinct("LocationId").alias("tiendas_activas"),
              F.count("*").alias("checks"),
              F.countDistinct("dt").alias("dias"),
              F.round(F.sum("gross"), 0).alias("venta_bruta"),
              F.round(F.sum("disc_item"), 0).alias("desc_nivel_item"),
              F.round(F.sum("disc_check"), 0).alias("desc_nivel_check"),
              F.round(F.sum("desc"), 0).alias("descuento_total"),
              F.round(F.sum("tip"), 0).alias("propinas"),
              F.avg(F.col("tiene_desc").cast("int")).alias("p"))
         .withColumn("pct_desc_sobre_venta", F.round(div("descuento_total", "venta_bruta") * 100, 2))
         .withColumn("pct_checks_con_desc", F.round(F.col("p") * 100, 2)).drop("p"))
display(kpi)
print("empleados distintos que aplican descuentos:", ds_m.select("LocationId", "EmployeeId").distinct().count())

# COMMAND ----------

# MAGIC %md ## 2. Tipos de descuento (Pareto) — base para proponer categorías

# COMMAND ----------

tipos = (ds.groupBy("DiscountName")
           .agg(F.count("*").alias("registros"),
                F.sum((F.col("Amount") == 0).cast("int")).alias("registros_monto_cero"),
                F.round(F.sum("Amount"), 2).alias("monto"),
                F.round(F.avg(F.when(F.col("Amount") > 0, F.col("Amount"))), 2).alias("monto_promedio"),
                F.countDistinct("LocationId").alias("tiendas"),
                F.sum((F.col("Nivel") == "check").cast("int")).alias("a_nivel_check"))
           .orderBy(F.desc("monto")))
total = tipos.agg(F.sum("monto")).collect()[0][0]
display(tipos.withColumn("pct_monto", F.round(F.col("monto") / F.lit(total) * 100, 2)))

# COMMAND ----------

# MAGIC %md ## 3. Canal (In-Store, To Go, Online, Delivery…)

# COMMAND ----------

canal = (ck.join(rc, "CheckRevenueCenterId", "left")
           .groupBy("Canal").agg(F.count("*").alias("checks"), F.sum("desc").alias("desc"),
                                 F.sum("gross").alias("gross"),
                                 F.avg(F.col("tiene_desc").cast("int")).alias("p"))
           .withColumn("pct_desc", F.round(div("desc", "gross") * 100, 2))
           .withColumn("pct_checks_con_desc", F.round(F.col("p") * 100, 2)).drop("p")
           .orderBy(F.desc("checks")))
display(canal)

# COMMAND ----------

# MAGIC %md ## 4. Tendencia: por día, día de la semana y hora

# COMMAND ----------

diario = (ck.groupBy("dt").agg(F.sum("desc").alias("desc"), F.sum("gross").alias("gross"))
            .withColumn("pct_desc", F.round(div("desc", "gross") * 100, 2)).orderBy("dt"))
display(diario)

semana = (ck.withColumn("dow", F.dayofweek("dt")).withColumn("dia", F.date_format("dt", "E"))
            .groupBy("dow", "dia").agg(F.sum("desc").alias("desc"), F.sum("gross").alias("gross"))
            .withColumn("pct_desc", F.round(div("desc", "gross") * 100, 2)).orderBy("dow"))
display(semana)

hora = (ck.withColumn("hora", F.hour(F.expr("try_to_timestamp(OpenTime)")))
          .groupBy("hora").agg(F.sum("desc").alias("desc"), F.sum("gross").alias("gross"),
                               F.count("*").alias("checks"))
          .withColumn("pct_desc", F.round(div("desc", "gross") * 100, 2)).orderBy("hora"))
display(hora)

# COMMAND ----------

# MAGIC %md ## 5. Por tienda: ¿qué sucursales descuentan fuera de lo normal?

# COMMAND ----------

tienda = (ck.groupBy("LocationId").agg(F.sum("desc").alias("desc"), F.sum("gross").alias("gross"),
                                       F.count("*").alias("checks"))
            .withColumn("pct_desc", F.round(div("desc", "gross") * 100, 2))
            .join(loc, "LocationId", "left")
            .orderBy(F.desc("pct_desc")))
display(tienda)
display(tienda.select(F.expr("percentile_approx(pct_desc, array(0.1, 0.25, 0.5, 0.75, 0.9))")
                       .alias("percentiles_pct_desc_tienda")))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Por empleado vs. su propia tienda (señal clave de abuso)
# MAGIC Venta del empleado = líneas con precio > 0 que registró. Se compara contra la mediana de **su** tienda.

# COMMAND ----------

MIN_LINEAS = 100

venta_emp = (it.filter("GrossPrice > 0").groupBy("LocationId", "EmployeeId")
               .agg(F.sum("GrossPrice").alias("gross_emp"), F.count("*").alias("lineas")))
desc_emp = (ds_m.groupBy("LocationId", "EmployeeId")
                .agg(F.sum("Amount").alias("desc_emp"), F.count("*").alias("n_desc")))

emp = (venta_emp.join(desc_emp, ["LocationId", "EmployeeId"], "left")
                .fillna(0, ["desc_emp", "n_desc"])
                .filter(F.col("lineas") >= MIN_LINEAS)
                .withColumn("pct_desc", div("desc_emp", "gross_emp") * 100))
mediana = emp.groupBy("LocationId").agg(F.expr("percentile_approx(pct_desc, 0.5)").alias("mediana_tienda"))
emp = (emp.join(mediana, "LocationId")
          .withColumn("veces_vs_tienda", F.round(div("pct_desc", "mediana_tienda"), 2))
          .orderBy(F.desc("veces_vs_tienda")))
display(emp)

display(emp.agg(
    F.count("*").alias("empleados"),
    F.sum((F.col("veces_vs_tienda") >= 2).cast("int")).alias("descuentan_2x_o_mas"),
    F.sum((F.col("veces_vs_tienda") >= 3).cast("int")).alias("descuentan_3x_o_mas"),
    F.round(F.sum(F.when(F.col("veces_vs_tienda") >= 3, F.col("desc_emp"))), 0).alias("monto_desc_3x")))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Antigüedad del empleado (idea de las notas)
# MAGIC Primero se valida con qué llave se une `EmployeeId` a `bronze_employees`. Se usa la de mayor cobertura.

# COMMAND ----------

dim = spark.table(f"{db}.bronze_employees")
ids = desc_emp.select("LocationId", "EmployeeId").distinct()
n_ids = ids.count()
cob_id = ids.join(dim.select(F.col("Id").alias("EmployeeId")).distinct(), "EmployeeId", "left_semi").count()
cob_loc = ids.join(dim.select("LocationId", F.col("LocationEmployeeId").alias("EmployeeId")).distinct(),
                   ["LocationId", "EmployeeId"], "left_semi").count()
print(f"empleados con descuentos: {n_ids} | cobertura por Id: {cob_id} | por LocationId+LocationEmployeeId: {cob_loc}")

# COMMAND ----------

if cob_loc >= cob_id:
    dim_k = dim.select("LocationId", F.col("LocationEmployeeId").alias("EmployeeId"), "HireDate")
    llave = ["LocationId", "EmployeeId"]
else:
    dim_k = dim.select(F.col("Id").alias("EmployeeId"), "HireDate")
    llave = ["EmployeeId"]
dim_k = dim_k.groupBy(*llave).agg(F.max("HireDate").alias("HireDate"))   # sin Name ni DateOfBirth

ant = (emp.join(dim_k, llave, "left")
          .withColumn("anios", F.floor(F.datediff(F.lit("2026-08-20"), F.to_date("HireDate")) / 365))
          .withColumn("rango_antiguedad",
              F.when(F.col("anios").isNull(), "Sin fecha")
               .when(F.col("anios") < 1, "< 1 año")
               .when(F.col("anios") < 3, "1-2 años")
               .when(F.col("anios") < 6, "3-5 años")
               .otherwise("6+ años")))
display(ant.groupBy("rango_antiguedad").agg(
            F.count("*").alias("empleados"),
            F.round(F.expr("percentile_approx(pct_desc, 0.5)"), 2).alias("pct_desc_mediana"),
            F.round(F.avg((F.col("veces_vs_tienda") >= 3).cast("int")) * 100, 1).alias("pct_empleados_3x"))
          .orderBy("rango_antiguedad"))

# COMMAND ----------

# MAGIC %md ## 8. Efectivo vs. tarjeta (¿más descuentos donde el dinero es más fácil de tomar?)

# COMMAND ----------

display(py.groupBy("PayCatName", "IsCashDebit", "IsCreditCard").count().orderBy(F.desc("count")))

pago = (ckp.groupBy("tipo_pago").agg(F.count("*").alias("checks"),
                                     F.sum("desc").alias("desc"), F.sum("gross").alias("gross"),
                                     F.avg(F.col("tiene_desc").cast("int")).alias("p"))
           .withColumn("pct_desc", F.round(div("desc", "gross") * 100, 2))
           .withColumn("pct_checks_con_desc", F.round(F.col("p") * 100, 2)).drop("p")
           .orderBy(F.desc("checks")))
display(pago)

# COMMAND ----------

# MAGIC %md
# MAGIC **Control:** ¿el efectivo sigue arriba si quitamos los tickets con comidas de empleados (que suelen pagarse en efectivo)?

# COMMAND ----------

emp_codes = ["EMP 50", "EMP 25%", "EMP 10%", "EMP 50%", "TRAINER", "MIT MEAL", "HQ DISC"]
chk_emp = ds.filter(F.col("DiscountName").isin(emp_codes)).select(*K).distinct()
sin_emp = ckp.join(chk_emp, K, "left_anti")
display(sin_emp.groupBy("tipo_pago")
          .agg(F.count("*").alias("checks"), F.sum("desc").alias("desc"),
               F.sum("gross").alias("gross"), F.avg(F.col("tiene_desc").cast("int")).alias("p"))
          .withColumn("pct_desc", F.round(div("desc", "gross") * 100, 2))
          .withColumn("pct_checks_con_desc", F.round(F.col("p") * 100, 2)).drop("p")
          .orderBy(F.desc("checks")))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Propina con vs. sin descuento (idea "tip + descuento")
# MAGIC Solo tickets con tarjeta. Propina / venta **bruta** (los clientes suelen dar propina sobre el monto antes del descuento).

# COMMAND ----------

tips = (ckp.filter("tipo_pago = 'Tarjeta crédito' AND gross > 0")
           .withColumn("tip_pct", div("tip", "gross") * 100)
           .withColumn("grupo", F.when(F.col("desc") == 0, "Sin descuento")
                                 .when(div("desc", "gross") < 0.25, "Desc < 25%")
                                 .otherwise("Desc ≥ 25%"))
           .groupBy("grupo")
           .agg(F.count("*").alias("checks"),
                F.round(F.expr("percentile_approx(tip_pct, 0.5)"), 2).alias("tip_pct_mediana"),
                F.round(F.avg("tip_pct"), 2).alias("tip_pct_promedio")))
display(tips)

# COMMAND ----------

# MAGIC %md ## 10. Autorizaciones: ¿quién aprueba los descuentos?

# COMMAND ----------

display(ds_m.agg(
    F.count("*").alias("descuentos"),
    F.sum(F.col("ManagerId").isNull().cast("int")).alias("gerente_nulo"),
    F.sum((F.col("ManagerId") == 0).cast("int")).alias("gerente_cero"),
    F.sum((F.col("EmployeeId") == F.col("ManagerId")).cast("int")).alias("autoaprobados"),
    F.round(F.sum(F.when(F.col("EmployeeId") == F.col("ManagerId"), F.col("Amount"))), 0).alias("monto_autoaprobado")))

pares = (ds_m.filter("ManagerId IS NOT NULL AND ManagerId != 0 AND EmployeeId != ManagerId")
             .groupBy("LocationId", "EmployeeId", "ManagerId")
             .agg(F.count("*").alias("veces"), F.round(F.sum("Amount"), 2).alias("monto"))
             .orderBy(F.desc("monto")))
display(pares)

# COMMAND ----------

# MAGIC %md ## 11. Voids: categorías y tipo de pago del ticket

# COMMAND ----------

vck = vd.join(tipo.select(*K, "tipo_pago"), K, "left").fillna("Sin pago", ["tipo_pago"])
display(vck.groupBy("VoidCategoryName", "tipo_pago")
           .agg(F.count("*").alias("registros"),
                F.sum((F.col("Amount") == 0).cast("int")).alias("monto_cero"),
                F.round(F.sum("Amount"), 2).alias("monto"))
           .orderBy(F.desc("monto")))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 12. Tickets "fantasma": 100% descontados, sin items o abiertos mucho tiempo
# MAGIC Patrones de las notas: cobrar y luego descontar/anular todo para que no aparezca en el efectivo esperado.

# COMMAND ----------

fx = (ckp.withColumn("min_abierto",
                     (F.unix_timestamp(F.expr("try_to_timestamp(CloseTime)")) -
                      F.unix_timestamp(F.expr("try_to_timestamp(OpenTime)"))) / 60)
         .withColumn("cien_pct_desc", (F.col("gross") > 0) & (F.col("venta_neta") <= 0.01))
         .withColumn("sin_items", F.col("n_items") == 0))

display(fx.agg(
    F.sum(F.col("cien_pct_desc").cast("int")).alias("tickets_100pct_desc"),
    F.round(F.sum(F.when(F.col("cien_pct_desc"), F.col("gross"))), 0).alias("monto_100pct_desc"),
    F.sum(F.col("sin_items").cast("int")).alias("tickets_sin_items"),
    F.sum((F.col("sin_items") & (F.col("voids") > 0)).cast("int")).alias("sin_items_con_voids"),
    F.expr("percentile_approx(min_abierto, array(0.5, 0.9, 0.99))").alias("minutos_abierto_p50_p90_p99")))

display(fx.withColumn("rango_min", F.when(F.col("min_abierto") < 60, "< 1 h")
                                    .when(F.col("min_abierto") < 120, "1-2 h")
                                    .when(F.col("min_abierto") < 240, "2-4 h")
                                    .otherwise("4 h +"))
          .groupBy("rango_min").agg(F.count("*").alias("checks"),
                                    F.round(F.sum("desc") / F.sum("gross") * 100, 2).alias("pct_desc"))
          .orderBy("rango_min"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conclusiones (para la slide final)
# MAGIC 1. …
# MAGIC 2. …
# MAGIC 3. …
# MAGIC
# MAGIC **Takeaway:** …
