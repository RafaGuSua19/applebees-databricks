"""Bronze: catálogos (tiendas, canales, empleados, items) leídos tal cual del volume."""
import dlt

SOURCE = spark.conf.get("source_path", "/Volumes/workspace/default/applebees")


def _leer(archivo):
    return spark.read.option("multiLine", "true").json(f"{SOURCE}/dimensions/*/{archivo}")


@dlt.table(name="bronze_locations", comment="Catálogo crudo de tiendas.")
def bronze_locations():
    return _leer("locations.json")


@dlt.table(name="bronze_revenue_centers", comment="Catálogo crudo de canales de venta.")
def bronze_revenue_centers():
    return _leer("revenueCenters.json")


@dlt.table(name="bronze_employees", comment="Catálogo crudo de empleados. Contiene PII: no se expone fuera de bronze.")
def bronze_employees():
    return _leer("employees.json")


@dlt.table(name="bronze_items", comment="Catálogo crudo de productos del menú.")
def bronze_items():
    return _leer("items.json")
