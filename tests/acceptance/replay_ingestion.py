# Databricks notebook source
"""Prueba opcional de Auto Loader con dos llegadas y una reejecución sin cambios."""
import json
import runpy
import sys
import types
from pathlib import Path
from uuid import uuid4

from pyspark.sql import functions as F

ROOT = Path.cwd().parents[1]
sys.path.insert(0, str(ROOT / "src/jobs"))
from quality_rules import qualified_schema


def passthrough(*args, **kwargs):
    return lambda fn: fn


original = sys.modules.get("dlt")
sys.modules["dlt"] = types.SimpleNamespace(table=passthrough, view=passthrough,
                                          expect=passthrough, expect_or_drop=passthrough)
try:
    parse = runpy.run_path(str(ROOT / "src/transformations/bronze/bronze_checks.py"))["parse_archivos"]
    build = runpy.run_path(str(ROOT / "src/transformations/silver/st_checks_cleaned.py"))["build_checks"]
finally:
    if original is None:
        del sys.modules["dlt"]
    else:
        sys.modules["dlt"] = original

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "")
catalog, schema = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
namespace = qualified_schema(catalog, schema)
if not schema.startswith("applebees_phase3_"):
    raise ValueError("Reproducir solamente en el esquema aislado de Fase 3")

case = uuid4().hex[:12]
spark.sql(f"CREATE VOLUME IF NOT EXISTS {namespace}.applebees_replay")
root = f"/Volumes/{catalog}/{schema}/applebees_replay/{case}"
source = f"{root}/facts/checks"
target = f"{namespace}.replay_bronze_{case}"


def ticket(day, ticket_id, optional_gaps=False):
    item = {"ItemId": 5, "GrossPrice": 100.0, "SoldPrice": 100.0}
    payment = {"Amount": 90.0, "Gratuity": 0.0, "PayCatName": "CASH"}
    record = {"Id": ticket_id, "LocationId": 7, "RevenueCenterId": 2,
              "BusinessDate": day, "ItemsSold": [item], "Payments": [payment],
              "Discounts": [{"Amount": 10.0, "DiscountName": "TEST"}], "Tax": [], "Voids": []}
    if optional_gaps:
        del item["ItemId"]
        del payment["Gratuity"]
        record["SchemaExtension"] = True
    return record


def land(day, rows):
    folder = f"{source}/brand=rmh/dt={day}"
    dbutils.fs.mkdirs(folder)
    dbutils.fs.put(f"{folder}/checks.json", json.dumps(rows), False)


def update():
    files = (spark.readStream.format("cloudFiles")
             .option("cloudFiles.format", "text").option("wholetext", "true")
             .option("cloudFiles.schemaLocation", f"{root}/schema")
             .load(source).select(F.col("_metadata.file_path").alias("_source_file"), "value"))
    query = (parse(files).writeStream.format("delta")
             .option("checkpointLocation", f"{root}/checkpoint")
             .trigger(availableNow=True).toTable(target))
    if not query.awaitTermination(300):
        query.stop()
        raise TimeoutError("El lote de reproducción excedió cinco minutos")


land("2026-08-19", [ticket("2026-08-19", 1)])
update()
assert spark.table(target).count() == 1

land("2026-08-20", [ticket("2026-08-20", 2, optional_gaps=True), ticket("2026-08-20", None)])
update()
bronze = spark.table(target)
assert bronze.count() == 3 and bronze.select("_source_file").distinct().count() == 2
assert bronze.filter("_rescued_data = 'llave_incompleta'").count() == 1
silver = build(bronze.filter("_rescued_data IS NULL"))
admitted = {r.CheckId: r for r in silver.collect()}
assert set(admitted) == {1, 2}
assert str(admitted[2].descuento) == "10.00" and admitted[2].tip is None
assert set(admitted[2]._dq_warnings) == {"campos_no_contemplados", "item_sin_id", "propina_desconocida"}

update()
assert spark.table(target).count() == 3
print(f"PASS: Auto Loader 1 → 3 → 3 filas Bronze; 2 tickets admitidos, 1 en cuarentena. Tabla: {target}")
