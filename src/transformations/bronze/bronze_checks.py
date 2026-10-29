"""Bronze: tickets crudos, ingeridos de forma incremental con Auto Loader."""
import dlt
from pyspark.sql import functions as F
from pyspark.sql import types as T

# Cada archivo diario es un solo arreglo JSON de 70-90 MB en una línea. Leerlo con el lector
# JSON multilínea agota la memoria por tarea en serverless, así que se lee como texto completo
# y se convierte con este esquema explícito (el mismo que se infirió en el EDA).
_DESC = "array<struct<Amount:double,DiscountId:bigint,DiscountName:string,EmployeeId:bigint,ManagerId:bigint>>"
ESQUEMA_TICKETS = f"""array<struct<
  BusinessDate:string, CloseTime:string,
  Discounts:{_DESC},
  Id:bigint,
  ItemsSold:array<struct<Discounts:{_DESC},EmployeeId:bigint,GrossPrice:double,ItemId:bigint,
    ItemMajorCatId:bigint,ItemMajorCatName:string,ItemName:string,ItemPLU:bigint,ItemSubCatId:bigint,
    ItemSubCatName:string,OrderTime:string,ParentSequence:bigint,PosSourceId:bigint,Quantity:double,
    RevenueCenterId:bigint,Seat:bigint,Sequence:bigint,SoldPrice:double>>,
  LocationId:bigint, LoyaltyId:string, OpenTime:string,
  Payments:array<struct<Amount:double,EmployeeId:bigint,Gratuity:double,IsCashDebit:boolean,
    IsCreditCard:boolean,IsGiftCard:boolean,IsGiftCert:boolean,IsNonPOS:boolean,IsPettyCash:boolean,
    PayCatName:string,PayCatNo:bigint,PaymentCategoryId:bigint,PosSourceId:bigint>>,
  RevenueCenterId:bigint, ServiceCharge:bigint, TableName:string,
  Tax:array<struct<Amount:double,TaxCategoryId:bigint,TaxCategoryName:string>>,
  TrafficCount:double,
  Voids:array<struct<Amount:double,EmployeeId:bigint,ItemId:bigint,ItemName:string,ItemPLU:bigint,
    ManagerId:bigint,Quantity:double,VoidCategoryId:bigint,VoidCategoryName:string>>
>>"""


# Conservamos cada objeto JSON antes de tiparlo. Los importes de origen siguen siendo
# double en bronze; silver los convierte a DECIMAL(18,2) antes de agregar.
ESQUEMA_TICKET = ESQUEMA_TICKETS[len("array<"):-1]
ESQUEMA_CON_CORRUPTO = ESQUEMA_TICKET[:-1] + ",_corrupt_record:string>"


def _unknown_fields_sql(schema, raw, depth=0):
    """Detecta campos extra en cualquier objeto, incluidos descuentos anidados."""
    known = ",".join("'" + field.name + "'" for field in schema.fields)
    checks = [f"size(array_except(json_object_keys({raw}), array({known}))) > 0"]
    for field in schema.fields:
        if isinstance(field.dataType, T.ArrayType) and isinstance(field.dataType.elementType, T.StructType):
            var = f"x{depth}"
            child = f"get_json_object({raw}, '$.{field.name}')"
            predicate = _unknown_fields_sql(field.dataType.elementType, var, depth + 1)
            checks.append(f"exists(from_json({child}, 'array<string>'), {var} -> ({predicate}))")
    return " OR ".join(f"coalesce(({check}), false)" for check in checks)


def parse_archivos(archivos):
    """Una fila por ticket o una fila de diagnóstico por archivo vacío/inválido."""
    records = archivos.withColumn("_records", F.from_json("value", "array<string>"))
    records = (records.select("_source_file", "value",
                              F.posexplode_outer("_records").alias("_record_index", "_raw_record"))
               .withColumn("_raw_record", F.coalesce("_raw_record", "value"))
               .drop("value"))
    parsed = records.withColumn("t", F.from_json("_raw_record", ESQUEMA_CON_CORRUPTO,
                                                 {"allowNonNumericNumbers": "false"}))
    schema = parsed.schema["t"].dataType
    unknown = F.expr(_unknown_fields_sql(schema, "_raw_record"))
    parsed = (parsed.withColumn("_unknown_fields", unknown)
              .select("t.*", "_raw_record", "_source_file", "_record_index", "_unknown_fields")
              .withColumn("brand", F.regexp_extract("_source_file", r"brand=([^/]+)", 1))
              .withColumn("dt", F.expr("try_cast(regexp_extract(_source_file, 'dt=([0-9]{4}-[0-9]{2}-[0-9]{2})', 1) AS DATE)")))
    invalid_values = """
      coalesce(exists(ItemsSold, i -> i IS NULL OR i.ItemId IS NULL OR
        i.GrossPrice IS NULL OR i.SoldPrice IS NULL OR isnan(i.GrossPrice) OR isnan(i.SoldPrice)), false)
      OR coalesce(exists(Discounts, d -> d IS NULL OR d.Amount IS NULL OR isnan(d.Amount)), false)
      OR coalesce(exists(ItemsSold, i -> exists(i.Discounts, d -> d IS NULL OR d.Amount IS NULL OR isnan(d.Amount))), false)
      OR coalesce(exists(Payments, p -> p IS NULL OR p.Amount IS NULL OR p.Gratuity IS NULL OR isnan(p.Amount) OR isnan(p.Gratuity)), false)
      OR coalesce(exists(Tax, t -> t IS NULL OR t.Amount IS NULL OR isnan(t.Amount)), false)
      OR coalesce(exists(Voids, v -> v IS NULL OR v.Amount IS NULL OR isnan(v.Amount)), false)
    """
    return (parsed.withColumn("_rescued_data",
                F.when(F.col("_record_index").isNull(), F.lit("archivo_vacio_o_json_invalido"))
                 .when(F.col("_corrupt_record").isNotNull() | F.json_object_keys("_raw_record").isNull(), F.lit("tipo_o_json_invalido"))
                 .when(F.col("_unknown_fields"), F.lit("campos_no_contemplados"))
                 .when(F.col("Id").isNull() | F.col("LocationId").isNull() | F.col("dt").isNull(), F.lit("llave_incompleta"))
                 .when(F.expr(invalid_values), F.lit("importe_o_detalle_incompleto"))
                 .when(F.expr("try_cast(substr(BusinessDate, 1, 10) AS DATE)").isNull()
                       | (F.expr("try_cast(substr(BusinessDate, 1, 10) AS DATE)") != F.col("dt")), F.lit("fecha_negocio_inconsistente")))
            .drop("_corrupt_record", "_unknown_fields")
            .withColumn("_ingested_at", F.current_timestamp()))


@dlt.table(
    name="bronze_checks",
    comment="Tickets y JSON original por registro; errores recuperables en _rescued_data. Auto Loader incremental.",
    cluster_by=["dt", "LocationId"], table_properties={"quality": "bronze"},
)
@dlt.expect("sin_datos_rescatados", "_rescued_data IS NULL")
@dlt.expect("con_fecha_de_negocio", "dt IS NOT NULL")
def bronze_checks():
    source = spark.conf.get("source_path", "/Volumes/workspace/default/applebees")
    archivos = (spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "text")
        .option("wholetext", "true")
        .option("cloudFiles.maxFilesPerTrigger", "1")
        .load(f"{source}/facts/checks")
        .select(F.col("_metadata.file_path").alias("_source_file"), "value"))
    return parse_archivos(archivos)


@dlt.view(name="valid_checks", comment="Admisión común de tickets y detalles; errores permanecen en bronze.")
def valid_checks():
    return spark.readStream.table("bronze_checks").filter("_rescued_data IS NULL")
