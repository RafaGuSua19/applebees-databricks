"""Silver: detalle del ticket (items, descuentos, pagos, voids) en tablas planas."""
import dlt
from pyspark.sql import functions as F

KEYS = ["CheckId", "LocationId", "CheckRevenueCenterId", "dt"]

COMPS = ["TASTE", "GST CORECT", "SERVERERR", "KITCHNERR", "WALKOUT", "TEMP", "WAIT", "SPEED",
         "NOSHOW", "WRNG DRINK", "WRNG STORE", "ENTRE CARD", "2F20STKCMP"]
EMPLEADO = ["EMP 50", "EMP 25%", "EMP 10%", "EMP 50%", "TRAINER", "MIT MEAL", "HQ DISC"]


def _checks():
    return (spark.readStream.table("bronze_checks")
            .withColumnRenamed("Id", "CheckId")
            .withColumnRenamed("RevenueCenterId", "CheckRevenueCenterId"))


@dlt.table(name="silver_items", comment="Una fila por línea de item. es_modificador = línea a $0 (salsas, cubiertos).",
           cluster_by=["dt", "LocationId"], table_properties={"quality": "silver"})
@dlt.expect_or_drop("item_con_id", "ItemId IS NOT NULL")
@dlt.expect("precio_no_negativo", "GrossPrice >= 0")
def silver_items():
    return (_checks().select(*KEYS, F.explode("ItemsSold").alias("i"))
            .select(*KEYS, "i.*").drop("Discounts")
            .withColumn("es_modificador", F.col("GrossPrice") == 0))


@dlt.table(name="silver_discounts",
           comment="Descuentos de nivel ticket e item (independientes), nombre normalizado y categoría de negocio.",
           cluster_by=["dt", "LocationId", "EmployeeId"], table_properties={"quality": "silver"})
@dlt.expect("monto_no_negativo", "Amount >= 0")
@dlt.expect("con_empleado", "EmployeeId IS NOT NULL")
def silver_discounts():
    c = _checks()
    nivel_check = (c.select(*KEYS, F.explode("Discounts").alias("d"))
                   .select(*KEYS, "d.*").withColumn("Nivel", F.lit("check")))
    nivel_item = (c.select(*KEYS, F.explode("ItemsSold").alias("i"))
                  .select(*KEYS, F.col("i.ItemId"), F.col("i.ItemName"), F.explode("i.Discounts").alias("d"))
                  .select(*KEYS, "ItemId", "ItemName", "d.*").withColumn("Nivel", F.lit("item")))
    nombre = F.upper(F.trim(F.col("DiscountName")))       # MARKETING / Marketing -> MARKETING
    return (nivel_check.unionByName(nivel_item, allowMissingColumns=True)
            .withColumn("DiscountName", nombre)
            .withColumn("categoria",
                        F.when(F.col("DiscountName").isin(COMPS), "Compensación")
                         .when(F.col("DiscountName").isin(EMPLEADO), "Empleado")
                         .when(F.col("DiscountName") == "MANAGER", "Manager discrecional")
                         .otherwise("Promoción / lealtad"))
            .withColumn("sin_gerente", F.col("ManagerId").isNull() | (F.col("ManagerId") == 0))
            .withColumn("autoaprobado", F.coalesce(F.col("EmployeeId") == F.col("ManagerId"), F.lit(False))))


@dlt.table(name="silver_payments", comment="Una fila por pago. Tip = -Gratuity (el sistema guarda la propina en negativo).",
           cluster_by=["dt", "LocationId"], table_properties={"quality": "silver"})
@dlt.expect("propina_no_negativa", "Tip >= 0")
def silver_payments():
    return (_checks().select(*KEYS, F.explode("Payments").alias("p"))
            .select(*KEYS, "p.*")
            .withColumn("PayCatName", F.upper(F.trim("PayCatName")))
            .withColumn("Tip", -F.col("Gratuity")))


@dlt.table(name="silver_voids", comment="Una fila por void (anulación de item).",
           cluster_by=["dt", "LocationId"], table_properties={"quality": "silver"})
@dlt.expect("void_no_negativo", "Amount >= 0")
def silver_voids():
    return (_checks().select(*KEYS, F.explode("Voids").alias("v"))
            .select(*KEYS, "v.*"))
