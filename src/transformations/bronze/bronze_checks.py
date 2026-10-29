"""Bronze: tickets crudos, ingeridos de forma incremental con Auto Loader."""
import dlt
from pyspark.sql import functions as F

SOURCE = spark.conf.get("source_path", "/Volumes/workspace/default/applebees")


@dlt.table(
    name="bronze_checks",
    comment="Tickets crudos de RMH Applebee's (1 JSON por día). Ingesta incremental con Auto Loader.",
    cluster_by=["dt", "LocationId"],
    table_properties={"quality": "bronze"},
)
@dlt.expect("sin_datos_rescatados", "_rescued_data IS NULL")
@dlt.expect("con_fecha_de_negocio", "dt IS NOT NULL")
def bronze_checks():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("multiLine", "true")
        .option("cloudFiles.inferColumnTypes", "true")
        .option("cloudFiles.partitionColumns", "brand,dt")
        .load(f"{SOURCE}/facts/checks")
        .withColumn("dt", F.to_date("dt"))
        .withColumn("_source_file", F.col("_metadata.file_path"))
        .withColumn("_ingested_at", F.current_timestamp())
    )
