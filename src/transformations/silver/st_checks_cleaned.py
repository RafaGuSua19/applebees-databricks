"""Silver: una fila por ticket, con totales conciliados, tipo de pago y banderas de riesgo."""
import dlt
from pyspark.sql import functions as F

APPS = "'DOORDASH','UBEREATS','GRUBHUB','POSTMATES','DELIVERLOGIC','BITESQUAD','EZCATER','FOODJA'"


def _suma(arr, campo):
    return F.expr(f"coalesce(aggregate({arr}, 0D, (acc, x) -> acc + coalesce(x.{campo}, 0D)), 0D)")


def _existe(cond):
    return F.coalesce(F.expr(f"exists(Payments, p -> {cond})"), F.lit(False))


@dlt.table(
    name="silver_checks",
    comment="Ticket limpio: llave LocationId+dt+CheckId, descuento total = item + check, propina positiva, tipo de pago por PayCatName.",
    cluster_by=["dt", "LocationId"],
    table_properties={"quality": "silver"},
)
@dlt.expect_or_drop("llave_completa", "LocationId IS NOT NULL AND dt IS NOT NULL AND CheckId IS NOT NULL")
@dlt.expect("venta_bruta_no_negativa", "gross >= 0")
@dlt.expect("conciliacion_cuadra", "abs(paid - (sold - disc_check + tax + tip)) <= 0.05")
@dlt.expect("horario_valido", "min_abierto IS NOT NULL AND min_abierto >= 0")
def silver_checks():
    c = (spark.readStream.table("bronze_checks")
         .withColumnRenamed("Id", "CheckId")
         .withColumnRenamed("RevenueCenterId", "CheckRevenueCenterId"))

    cash = _existe("upper(p.PayCatName) = 'CASH'")
    card = _existe("p.IsCreditCard")
    gift = _existe("p.IsGiftCard")
    app = _existe(f"upper(p.PayCatName) IN ({APPS})")
    n_pagos = F.coalesce(F.size("Payments"), F.lit(0))

    tipo_pago = (F.when(n_pagos <= 0, "Sin pago")
                 .when(app, "App delivery")
                 .when(cash & ~card, "Efectivo")
                 .when(card & ~cash, "Tarjeta crédito")
                 .when(card & cash, "Mixto")
                 .when(gift, "Gift card")
                 .otherwise("Otro"))

    minutos = (F.unix_timestamp(F.expr("try_to_timestamp(CloseTime)"))
               - F.unix_timestamp(F.expr("try_to_timestamp(OpenTime)"))) / 60

    return (
        c.select(
            "CheckId", "LocationId", "CheckRevenueCenterId", "dt", "OpenTime", "CloseTime",
            "TableName", "TrafficCount", "ServiceCharge",        # LoyaltyId se descarta: 100% nulo
            F.greatest(F.coalesce(F.size("ItemsSold"), F.lit(0)), F.lit(0)).alias("n_items"),
            F.greatest(F.coalesce(F.expr("size(filter(ItemsSold, x -> x.GrossPrice > 0))"), F.lit(0)), F.lit(0)).alias("n_items_con_precio"),
            _suma("ItemsSold", "GrossPrice").alias("gross"),
            _suma("ItemsSold", "SoldPrice").alias("sold"),
            F.expr("""coalesce(aggregate(ItemsSold, 0D, (acc, x) -> acc +
                      coalesce(aggregate(x.Discounts, 0D, (a, d) -> a + coalesce(d.Amount, 0D)), 0D)), 0D)""").alias("disc_item"),
            _suma("Discounts", "Amount").alias("disc_check"),
            _suma("Voids", "Amount").alias("voids"),
            F.greatest(F.coalesce(F.size("Voids"), F.lit(0)), F.lit(0)).alias("n_voids"),
            _suma("Tax", "Amount").alias("tax"),
            _suma("Payments", "Amount").alias("paid"),
            (-_suma("Payments", "Gratuity")).alias("tip"),      # Gratuity viene negativa por diseño
            tipo_pago.alias("tipo_pago"),
            minutos.alias("min_abierto"),
            "_source_file",
        )
        .withColumn("descuento", F.col("disc_item") + F.col("disc_check"))
        .withColumn("venta_neta", F.col("sold") - F.col("disc_check"))
        .withColumn("cien_pct_desc", (F.col("gross") > 0) & (F.col("venta_neta") <= 0.01))
        .withColumn("abierto_4h", F.col("min_abierto") >= 240)
    )
