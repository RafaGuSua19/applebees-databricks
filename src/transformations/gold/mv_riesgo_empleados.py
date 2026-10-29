"""Gold: motor de riesgo por empleado (reglas explicables, comparando contra su propia tienda)."""
import dlt
from pyspark.sql import functions as F

K = ["LocationId", "dt", "CheckId"]
MIN_LINEAS = 100


def _div(a, b):
    return F.expr(f"try_divide({a}, {b})")


@dlt.table(
    name="gold_riesgo_empleados",
    comment="Score de riesgo (0-7) por empleado: % de descuento vs su tienda, peso del efectivo, MANAGER/WALKOUT, sin gerente, autoaprobados y tickets abiertos 4 h+.",
    cluster_by=["LocationId"],
)
@dlt.expect("score_valido", "score_riesgo BETWEEN 0 AND 7")
def gold_riesgo_empleados():
    items = spark.read.table("silver_items").filter("GrossPrice > 0")
    desc = spark.read.table("silver_discounts").filter("Amount > 0")
    checks = spark.read.table("silver_checks").select(*K, "tipo_pago", "abierto_4h")
    emp = spark.read.table("silver_employees")
    corte = checks.agg(F.max("dt").alias("fecha_corte"))

    venta = (items.groupBy("LocationId", "EmployeeId")
             .agg(F.sum("GrossPrice").alias("venta_emp"), F.count("*").alias("lineas")))

    llave_ticket = F.concat_ws("|", *[F.col(k).cast("string") for k in K])
    d = (desc.join(checks, K, "left")
         .groupBy("LocationId", "EmployeeId")
         .agg(F.sum("Amount").alias("desc_emp"),
              F.count("*").alias("n_desc"),
              F.sum(F.when(F.col("tipo_pago") == "Efectivo", F.col("Amount")).otherwise(0)).alias("desc_efectivo"),
              F.sum(F.when(F.col("DiscountName").isin("MANAGER", "WALKOUT"), F.col("Amount")).otherwise(0)).alias("desc_manager_walkout"),
              F.sum(F.col("sin_gerente").cast("int")).alias("n_sin_gerente"),
              F.sum(F.col("autoaprobado").cast("int")).alias("n_autoaprobados"),
              F.countDistinct(F.when(F.col("abierto_4h"), llave_ticket)).alias("tickets_4h_con_desc")))

    num = ["desc_emp", "n_desc", "desc_efectivo", "desc_manager_walkout",
           "n_sin_gerente", "n_autoaprobados", "tickets_4h_con_desc"]
    e = (venta.join(d, ["LocationId", "EmployeeId"], "left").fillna(0, num)
         .filter(F.col("lineas") >= MIN_LINEAS)
         .withColumn("pct_desc", _div("desc_emp", "venta_emp")))

    mediana = e.groupBy("LocationId").agg(F.expr("percentile_approx(pct_desc, 0.5)").alias("mediana_tienda"))

    e = (e.join(mediana, "LocationId")
         .withColumn("veces_vs_tienda", _div("pct_desc", "mediana_tienda"))
         .withColumn("pct_efectivo", _div("desc_efectivo", "desc_emp"))
         .withColumn("pct_manager_walkout", _div("desc_manager_walkout", "desc_emp"))
         .withColumn("pct_sin_gerente", _div("n_sin_gerente", "n_desc")))

    score = (F.when(F.col("veces_vs_tienda") >= 3, 2).when(F.col("veces_vs_tienda") >= 2, 1).otherwise(0)
             + F.when(F.col("pct_efectivo") >= 0.5, 1).otherwise(0)
             + F.when(F.col("pct_manager_walkout") >= 0.3, 1).otherwise(0)
             + F.when(F.col("pct_sin_gerente") >= 0.1, 1).otherwise(0)
             + F.when(F.col("n_autoaprobados") > 0, 1).otherwise(0)
             + F.when(F.col("tickets_4h_con_desc") >= 5, 1).otherwise(0))

    return (e.withColumn("score_riesgo", score)
            .withColumn("nivel_riesgo", F.when(F.col("score_riesgo") >= 4, "Alto")
                                         .when(F.col("score_riesgo") >= 2, "Medio")
                                         .otherwise("Bajo"))
            .join(emp.select("EmployeeId", "HireDate"), "EmployeeId", "left")
            .crossJoin(corte)
            .withColumn("anios_antiguedad",
                        F.floor(F.datediff(F.col("fecha_corte"), F.to_date("HireDate")) / 365))
            .drop("fecha_corte"))
