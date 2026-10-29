"""Silver: catálogos limpios. Los datos personales de empleados se excluyen (gobierno de datos)."""
import dlt
from pyspark.sql import functions as F


@dlt.table(name="silver_locations", comment="Tiendas: id, nombre, apertura/cierre y zona horaria.")
@dlt.expect_or_drop("tienda_con_id", "LocationId IS NOT NULL")
def silver_locations():
    return (spark.read.table("bronze_locations")
            .select(F.col("Id").alias("LocationId"), F.col("Name").alias("Tienda"),
                    "OpenDate", "ClosedDate", "TimeZoneName")
            .dropDuplicates(["LocationId"]))


@dlt.table(name="silver_revenue_centers", comment="Canales de venta (In-Store, To Go, Online, Delivery...).")
@dlt.expect_or_drop("canal_con_id", "CheckRevenueCenterId IS NOT NULL")
def silver_revenue_centers():
    return (spark.read.table("bronze_revenue_centers")
            .select(F.col("Id").alias("CheckRevenueCenterId"), F.col("Name").alias("Canal"))
            .dropDuplicates(["CheckRevenueCenterId"]))


@dlt.table(name="silver_employees",
           comment="Empleados SIN datos personales (se excluyen Name, DateOfBirth e IsMinor). Llave: EmployeeId = Id.")
@dlt.expect_or_drop("empleado_con_id", "EmployeeId IS NOT NULL")
def silver_employees():
    return (spark.read.table("bronze_employees")
            .groupBy(F.col("Id").alias("EmployeeId"))
            .agg(F.max("HireDate").alias("HireDate"),
                 F.max("PrimaryJobID").alias("PrimaryJobID")))
