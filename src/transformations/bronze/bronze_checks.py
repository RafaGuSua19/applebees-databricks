"""Bronze: tickets crudos, ingeridos de forma incremental con Auto Loader."""
import dlt
from pyspark.sql import functions as F

SOURCE = spark.conf.get("source_path", "/Volumes/workspace/default/applebees")

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


@dlt.table(
    name="bronze_checks",
    comment="Tickets crudos de RMH Applebee's (1 JSON por día). Ingesta incremental con Auto Loader.",
    cluster_by=["dt", "LocationId"],
    table_properties={"quality": "bronze"},
)
@dlt.expect("sin_datos_rescatados", "_rescued_data IS NULL")
@dlt.expect("con_fecha_de_negocio", "dt IS NOT NULL")
def bronze_checks():
    archivos = (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "text")
        .option("wholetext", "true")
        .option("cloudFiles.maxFilesPerTrigger", "1")   # un archivo por lote para no agotar la memoria
        .load(f"{SOURCE}/facts/checks")
        .select(F.col("_metadata.file_path").alias("_source_file"),
                F.col("value"),
                F.from_json("value", ESQUEMA_TICKETS).alias("tickets"))
    )
    # Si un archivo no tiene el formato esperado, queda una fila con _rescued_data para que la
    # expectation y la compuerta de calidad lo detecten
    return (
        archivos.select(
            "_source_file",
            F.when(F.col("tickets").isNull(), F.substring("value", 1, 1000)).alias("_rescued_data"),
            F.explode_outer("tickets").alias("t"))
        .select("t.*", "_rescued_data", "_source_file")
        .withColumn("brand", F.regexp_extract("_source_file", r"brand=([^/]+)", 1))
        .withColumn("dt", F.to_date(F.regexp_extract("_source_file", r"dt=(\d{4}-\d{2}-\d{2})", 1)))
        .withColumn("_ingested_at", F.current_timestamp())
    )
