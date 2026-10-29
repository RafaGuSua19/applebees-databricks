# Databricks notebook source
# Opt-in: ejecutar con `databricks bundle run validation_job -t qa`.
# Usa Spark real, datos sintéticos en memoria y lecturas del esquema de QA.
import copy
import json
import runpy
import sys
import types
from pathlib import Path

from pyspark.sql import functions as F

ROOT = Path.cwd().parents[1]
assert (ROOT / "src").exists(), f"Raíz de código no encontrada: {ROOT}"
sys.path.insert(0, str(ROOT / "src" / "jobs"))
from quality_rules import quality_errors, qualified_schema

def decorator(*args, **kwargs):
    return lambda fn: fn

original_dlt = sys.modules.get("dlt")
sys.modules["dlt"] = types.SimpleNamespace(table=decorator, view=decorator, expect=decorator,
                                          expect_or_drop=decorator, expect_or_fail=decorator)
try:
    bronze = runpy.run_path(str(ROOT / "src/transformations/bronze/bronze_checks.py"), init_globals={"spark": spark})
    checks_code = runpy.run_path(str(ROOT / "src/transformations/silver/st_checks_cleaned.py"), init_globals={"spark": spark})
    details = runpy.run_path(str(ROOT / "src/transformations/silver/st_details_cleaned.py"), init_globals={"spark": spark})
    risk = runpy.run_path(str(ROOT / "src/transformations/gold/mv_riesgo_empleados.py"), init_globals={"spark": spark})
finally:
    if original_dlt is None:
        del sys.modules["dlt"]
    else:
        sys.modules["dlt"] = original_dlt

base = {"Id": 1, "LocationId": 7, "RevenueCenterId": 2, "BusinessDate": "2026-08-20",
        "OpenTime": "2026-08-20 10:00:00", "CloseTime": "2026-08-20 14:00:00",
        "ItemsSold": [{"ItemId": 3, "EmployeeId": 11, "GrossPrice": 10.10, "SoldPrice": 9.10,
                       "Discounts": [{"Amount": 1, "EmployeeId": 11, "ManagerId": 11, "DiscountName": " Manager "}]}],
        "Discounts": [{"Amount": 2, "EmployeeId": 0, "ManagerId": 0, "DiscountName": "Taste"}],
        "Payments": [{"Amount": 8.10, "Gratuity": -1, "PayCatName": " cash ", "IsCreditCard": False}],
        "Tax": [], "Voids": []}
cases = [("valid", json.dumps([base]), None)]
def case(name, mutate, expected):
    obj = copy.deepcopy(base)
    mutate(obj)
    cases.append((name, json.dumps([obj]), expected))

case("extra_root", lambda x: x.update(UnexpectedField=7), "campos_no_contemplados")
case("extra_nested", lambda x: x["ItemsSold"][0]["Discounts"][0].update(UnexpectedField=7), "campos_no_contemplados")
case("bad_id", lambda x: x.update(Id="invalid"), "tipo_o_json_invalido")
case("bad_money", lambda x: x["ItemsSold"][0].update(GrossPrice="invalid"), "tipo_o_json_invalido")
case("null_money", lambda x: x["ItemsSold"][0].update(SoldPrice=None), "importe_o_detalle_incompleto")
case("missing_id", lambda x: x.pop("Id"), "llave_incompleta")
case("wrong_date", lambda x: x.update(BusinessDate="2026-08-19"), "fecha_negocio_inconsistente")
case("nan", lambda x: x["ItemsSold"][0].update(GrossPrice=float("nan")), "tipo_o_json_invalido")
case("null_detail", lambda x: x.update(ItemsSold=[None]), "importe_o_detalle_incompleto")
cases.extend([("empty", "[]", "archivo_vacio_o_json_invalido"),
              ("malformed", "[broken", "archivo_vacio_o_json_invalido"),
              ("scalar", "[5]", "tipo_o_json_invalido"),
              ("object_instead_array", json.dumps(base), "archivo_vacio_o_json_invalido"),
              ("partial_malformed", "[" + json.dumps(base) + ",broken]", "archivo_vacio_o_json_invalido")])
input_df = spark.createDataFrame([(f"/fixtures/{name}/brand=rmh/dt=2026-08-20/data.json", raw)
                                 for name, raw, _ in cases], "_source_file string, value string")
parsed = bronze["parse_archivos"](input_df)
actual = {row._source_file.split("/")[2]: row._rescued_data
          for row in parsed.select("_source_file", "_rescued_data").collect()}
for name, raw, expected in cases:
    assert actual[name] == expected, (name, actual[name], expected)
print(f"PASS: {len(cases)} casos del parser (incluye campos anidados, tipos, nulos y archivo vacío)")

valid = parsed.filter("_rescued_data IS NULL")
checks = checks_code["build_checks"](valid)
row = checks.collect()[0]
assert str(row.gross) == "10.10" and str(row.descuento) == "3.00", row
assert str(row.venta_neta) == "7.10" and str(row.tip) == "1.00", row
assert row.paid == row.venta_neta + row.tax + row.tip
assert row.tipo_pago == "Efectivo" and row.abierto_4h
assert "decimal" in checks.schema["gross"].dataType.simpleString()
check_input = valid.withColumnRenamed("Id", "CheckId").withColumnRenamed("RevenueCenterId", "CheckRevenueCenterId")
discounts = details["build_discounts"](check_input)
found = {r.EmployeeId: r for r in discounts.collect()}
assert not found[0].autoaprobado and found[0].sin_gerente
assert found[11].autoaprobado and found[11].DiscountName == "MANAGER"
# Regresión del límite de un centavo: 0.10 + 0.20 - 0.29 debe ser exactamente 0.01.
cent = copy.deepcopy(base)
cent["ItemsSold"] = [{"ItemId": 3, "EmployeeId": 11, "GrossPrice": value,
                      "SoldPrice": value, "Discounts": []} for value in (0.10, 0.20)]
cent["Discounts"] = [{"Amount": 0.29, "EmployeeId": 11, "ManagerId": 12}]
cent["Payments"] = [{"Amount": 0.01, "Gratuity": 0, "PayCatName": "CASH"}]
cent_df = spark.createDataFrame([("/fixtures/cent/brand=rmh/dt=2026-08-20/data.json", json.dumps([cent]))],
                                "_source_file string, value string")
cent_row = checks_code["build_checks"](bronze["parse_archivos"](cent_df)).first()
assert str(cent_row.gross) == "0.30" and str(cent_row.venta_neta) == "0.01" and cent_row.cien_pct_desc
print("PASS: importes decimales, límite de un centavo, no doble conteo, efectivo, 4h y autoaprobaciones")

items = spark.createDataFrame([(7, employee, 10.0) for employee in (0, 11, 999) for _ in range(100)],
                              "LocationId long, EmployeeId long, GrossPrice double")
employees = spark.createDataFrame([(11, "2020-01-01")], "EmployeeId long, HireDate string")
scored = risk["build_risk"](items, discounts, checks, employees).collect()
assert len(scored) == 1 and scored[0].EmployeeId == 11
assert scored[0].score_riesgo == 3, scored
print("PASS: ID cero y empleado fuera del catálogo excluidos; score esperado")

# El dataset completo debe haberse publicado antes de esta prueba.
dbutils.widgets.text("validate_dataset", "true")
if dbutils.widgets.get("validate_dataset") == "false":
    dbutils.notebook.exit("SYNTHETIC VALIDATION PASSED")
dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "applebees_qa")
db = qualified_schema(dbutils.widgets.get("catalog"), dbutils.widgets.get("schema"))
metrics = [r.asDict() for r in spark.table(f"{db}.gold_calidad_datos").collect()]
assert not quality_errors(metrics), quality_errors(metrics)
assert metrics[0]["tickets"] == 2142846, metrics
assert metrics[0]["archivos"] == 115 and metrics[0]["dias"] == 115
sums = spark.table(f"{db}.gold_kpis_diarios").agg(F.sum("tickets"), F.sum("venta_bruta"), F.sum("descuento")).first()
assert sums[0] == metrics[0]["tickets"]
assert str(sums[1]) == "87317743.68", sums
assert str(sums[2]) == "3023167.75", sums
ratio_errors = spark.table(f"{db}.gold_kpis_diarios").filter("""
  NOT (pct_desc <=> CAST(try_divide(CAST(descuento AS DECIMAL(24,2)),
                                   CAST(venta_bruta AS DECIMAL(24,2))) AS DECIMAL(18,9)))
""").count()
assert ratio_errors == 0, f"{ratio_errors} tasas inconsistentes tras materializar/incrementar"
for table in ("silver_employees", "gold_riesgo_empleados"):
    assert not {"Name", "DateOfBirth", "IsMinor"}.intersection(spark.table(f"{db}.{table}").columns)
print("PASS: calidad, reconciliación entre capas, totales del dataset y privacidad")
print("VALIDATION PASSED")
