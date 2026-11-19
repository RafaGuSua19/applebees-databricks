# Databricks notebook source
# Simulador de días nuevos de tickets.
#
# Genera días posteriores al dataset (21 ago 2026 en adelante) remuestreando un día real del mismo
# día de la semana, y siembra empleados con patrones de abuso conocidos. Los archivos se escriben con
# la misma estructura que la fuente, así que el pipeline los ingiere con Auto Loader sin cambios.
#
# Acciones:
#   preparar -> crea el volumen y el esquema de demo y copia catálogos + los últimos N días reales.
#   generar  -> escribe los siguientes N días simulados y registra la bitácora.
# La fuente original solo se lee.
import json
import os
from datetime import date, timedelta

from pyspark.sql import functions as F

from reglas_simulacion import (aplicar_abuso, asignar_patrones, elegir_empleados, mover_ticket,
                               rng_para, tiene_venta)

dbutils.widgets.dropdown("accion", "generar", ["preparar", "generar"])
dbutils.widgets.text("origen", "/Volumes/workspace/default/applebees")
dbutils.widgets.text("destino", "/Volumes/workspace/default/applebees_demo")
dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "applebees_demo")
dbutils.widgets.text("dias_historia", "35")
dbutils.widgets.text("n_dias", "1")
dbutils.widgets.text("n_empleados", "8")
dbutils.widgets.text("tickets_por_empleado", "15")
dbutils.widgets.text("semilla", "2026")

ACCION = dbutils.widgets.get("accion")
ORIGEN = dbutils.widgets.get("origen").rstrip("/")
DESTINO = dbutils.widgets.get("destino").rstrip("/")
CATALOGO = dbutils.widgets.get("catalog")
ESQUEMA_DEMO = dbutils.widgets.get("schema")
ESQUEMA = f"{CATALOGO}.{ESQUEMA_DEMO}"
DIAS_HISTORIA = int(dbutils.widgets.get("dias_historia"))
N_DIAS = int(dbutils.widgets.get("n_dias"))
N_EMPLEADOS = int(dbutils.widgets.get("n_empleados"))
TICKETS_POR_EMPLEADO = int(dbutils.widgets.get("tickets_por_empleado"))
SEMILLA = dbutils.widgets.get("semilla")

TABLA_VERDAD = f"{ESQUEMA}.sim_fraude_sembrado"
TABLA_BITACORA = f"{ESQUEMA}.sim_bitacora"
TABLA_TICKETS = f"{ESQUEMA}.sim_tickets_sembrados"

# El job se ejecuta como su propietario aunque otro integrante lo lance con parámetros.
if (ORIGEN != "/Volumes/workspace/default/applebees" or
        DESTINO != "/Volumes/workspace/default/applebees_demo" or ESQUEMA != "workspace.applebees_demo"):
    raise ValueError("El simulador usa el origen oficial y su volumen y esquema dedicados applebees_demo")
if min(DIAS_HISTORIA, N_DIAS, N_EMPLEADOS, TICKETS_POR_EMPLEADO) < 1:
    raise ValueError("Los días, empleados y tickets por empleado deben ser positivos")

ESTRUCTURA_BITACORA = ("dt date, dia_referencia date, archivo string, tickets_referencia long, "
                      "tickets_generados long, tickets_con_abuso long, monto_sembrado double")
ESTRUCTURA_TICKETS = "dt date, LocationId long, CheckId long, EmployeeId long, patron string, monto_sembrado double"

# COMMAND ----------

def _local(ruta):
    return ruta.replace("dbfs:", "").rstrip("/")


def existe(ruta):
    try:
        dbutils.fs.ls(ruta)
        return True
    except Exception:
        return False


def listar_fechas(base):
    """{fecha: carpeta} de todos los días bajo facts/checks/brand=*/dt=*."""
    fechas = {}
    if not existe(f"{base}/facts/checks"):
        return fechas
    for marca in dbutils.fs.ls(f"{base}/facts/checks"):
        if marca.name.startswith("brand="):
            for dia in dbutils.fs.ls(marca.path):
                if dia.name.startswith("dt="):
                    archivo = f"{_local(dia.path)}/checks.json"
                    if existe(archivo):
                        fechas[date.fromisoformat(dia.name[3:13])] = archivo
    return fechas

# COMMAND ----------

def preparar():
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {ESQUEMA}")
    spark.sql("CREATE VOLUME IF NOT EXISTS workspace.default.applebees_demo")
    spark.sql(f"CREATE TABLE IF NOT EXISTS {TABLA_BITACORA} ({ESTRUCTURA_BITACORA}, generado_en timestamp) USING DELTA")
    spark.sql(f"CREATE TABLE IF NOT EXISTS {TABLA_TICKETS} ({ESTRUCTURA_TICKETS}) USING DELTA")
    if not existe(f"{DESTINO}/dimensions"):
        if not dbutils.fs.cp(f"{ORIGEN}/dimensions", f"{DESTINO}/dimensions", recurse=True):
            raise OSError("Falló la copia de los catálogos de referencia")
    reales = listar_fechas(ORIGEN)
    if len(reales) < DIAS_HISTORIA:
        raise ValueError(f"Hay {len(reales)} archivos históricos; se solicitaron {DIAS_HISTORIA}")
    copiados = 0
    for dia in sorted(reales)[-DIAS_HISTORIA:]:
        carpeta = f"{DESTINO}/facts/checks/brand=rmh/dt={dia}"
        archivo = f"{carpeta}/checks.json"
        if not existe(archivo):
            dbutils.fs.mkdirs(carpeta)
            if not dbutils.fs.cp(reales[dia], archivo):
                raise OSError(f"Falló la copia de {dia}")
            copiados += 1
    print(f"Destino listo: {copiados} días copiados ({DIAS_HISTORIA} más recientes).")
    print("Siguiente paso: correr el pipeline del target demo y después este notebook con accion=generar.")

# COMMAND ----------

def empleados_sembrados(primer_dia):
    """Crea la tabla de verdad la primera vez; después siempre usa los mismos empleados."""
    if not spark.catalog.tableExists(TABLA_VERDAD):
        candidatos = spark.sql(f"""
            SELECT EmployeeId, LocationId FROM {ESQUEMA}.gold_riesgo_empleados
            WHERE nivel_riesgo = 'Bajo' AND lineas >= 300""").collect()
        elegidos = elegir_empleados([(r.EmployeeId, r.LocationId) for r in candidatos],
                                    N_EMPLEADOS, rng_para(SEMILLA, "empleados"))
        filas = [(e, l, p, primer_dia) for e, l, p in asignar_patrones(elegidos)]
        (spark.createDataFrame(filas, "EmployeeId long, LocationId long, patron string, fecha_inicio date")
         .join(spark.table(f"{ESQUEMA}.gold_riesgo_empleados")
               .select("EmployeeId", "LocationId", F.col("score_riesgo").alias("score_inicial"),
                       F.col("nivel_riesgo").alias("nivel_inicial")), ["EmployeeId", "LocationId"])
         .withColumn("creado_en", F.current_timestamp())
         .write.saveAsTable(TABLA_VERDAD))
    return {r.LocationId: (r.EmployeeId, r.patron) for r in spark.table(TABLA_VERDAD).collect()}


def catalogos_descuento(sembrados):
    ids = {r.DiscountName: (r.DiscountName, r.DiscountId) for r in spark.sql(f"""
        SELECT DiscountName, max_by(DiscountId, n) AS DiscountId FROM (
          SELECT DiscountName, DiscountId, count(*) AS n FROM {ESQUEMA}.silver_discounts
          WHERE DiscountName IN ('MANAGER', 'WALKOUT') GROUP BY ALL)
        GROUP BY DiscountName""").collect()}
    excluir = ",".join(str(e) for e, _ in sembrados.values()) or "0"
    gerentes = {r.LocationId: r.ManagerId for r in spark.sql(f"""
        SELECT LocationId, max_by(ManagerId, n) AS ManagerId FROM (
          SELECT LocationId, ManagerId, count(*) AS n FROM {ESQUEMA}.silver_discounts
          WHERE ManagerId > 0 AND ManagerId NOT IN ({excluir}) GROUP BY ALL)
        GROUP BY LocationId""").collect()}
    return ids, gerentes

# COMMAND ----------

def generar_dia(dia, reales, sembrados, ids_descuento, gerentes):
    rng = rng_para(SEMILLA, dia)
    referencia = rng.choice(sorted(d for d in reales if d.weekday() == dia.weekday()))
    dias = (dia - referencia).days

    tickets = (spark.read.option("wholetext", "true").text(reales[referencia])
               .select(F.explode(F.from_json("value", "array<string>")).alias("t")))
    por_tienda = {r[0]: r[1] for r in tickets.groupBy(
        F.get_json_object("t", "$.LocationId").cast("long")).count().collect()}
    conservar = {loc: rng_para(SEMILLA, dia, "tienda", loc).uniform(0.85, 1.0) for loc in por_tienda}

    pago = (tickets.select(F.explode(F.from_json(F.get_json_object("t", "$.Payments"), "array<string>")).alias("p"))
            .filter(F.upper(F.trim(F.get_json_object("p", "$.PayCatName"))) == "CASH").limit(1).collect())
    plantilla_efectivo = json.loads(pago[0].p) if pago else None

    staging = f"{DESTINO}/_staging/dt={dia}.json"
    os.makedirs(os.path.dirname(staging), exist_ok=True)
    n, n_abuso, monto_abuso, sembrados_dia = 0, 0, 0, []
    with open(staging, "w") as f:
        f.write("[")
        for fila in tickets.toLocalIterator():
            t = json.loads(fila.t)
            loc = t.get("LocationId")
            r = rng_para(SEMILLA, dia, loc, t.get("Id"))
            if r.random() > conservar.get(loc, 1.0):
                continue
            mover_ticket(t, dias)
            if loc in sembrados and tiene_venta(t) and r.random() < TICKETS_POR_EMPLEADO / por_tienda[loc]:
                emp, patron = sembrados[loc]
                monto = aplicar_abuso(t, emp, patron, plantilla_efectivo, ids_descuento, gerentes.get(loc), r)
                if monto is not None:
                    n_abuso += 1
                    monto_abuso += float(monto)
                    sembrados_dia.append((dia, loc, t.get("Id"), emp, patron, float(monto)))
            f.write(("," if n else "") + json.dumps(t, separators=(",", ":")))
            n += 1
        f.write("]")

    carpeta = f"{DESTINO}/facts/checks/brand=rmh_sim/dt={dia}"
    archivo = f"{carpeta}/checks.json"
    if existe(archivo):
        raise FileExistsError(archivo)
    # Registrar primero las etiquetas por día permite reconstruirlas si falla la publicación.
    filtro = f"dt = DATE '{dia}'"
    (spark.createDataFrame([(dia, referencia, archivo, sum(por_tienda.values()), n, n_abuso,
                             round(monto_abuso, 2))], ESTRUCTURA_BITACORA)
     .withColumn("generado_en", F.current_timestamp())
     .write.mode("overwrite").option("replaceWhere", filtro).saveAsTable(TABLA_BITACORA))
    (spark.createDataFrame(sembrados_dia, ESTRUCTURA_TICKETS)
     .write.mode("overwrite").option("replaceWhere", filtro).saveAsTable(TABLA_TICKETS))
    dbutils.fs.mkdirs(carpeta)
    if not dbutils.fs.mv(staging, archivo):
        raise OSError(f"Falló la publicación de {archivo}")
    print(f"{dia}: {n:,} tickets (referencia {referencia}), {n_abuso} con abuso sembrado por ${monto_abuso:,.2f}")


def generar():
    if not spark.catalog.tableExists(f"{ESQUEMA}.gold_riesgo_empleados"):
        raise RuntimeError(f"No existe {ESQUEMA}.gold_riesgo_empleados: primero accion=preparar y correr el pipeline")
    reales = listar_fechas(ORIGEN)
    actuales = listar_fechas(DESTINO)
    if not actuales:
        raise RuntimeError(f"{DESTINO} no tiene días: correr primero accion=preparar")
    siguiente = max(actuales) + timedelta(days=1)
    sembrados = empleados_sembrados(siguiente)
    ids_descuento, gerentes = catalogos_descuento(sembrados)
    faltan = {"MANAGER", "WALKOUT"} - set(ids_descuento)
    if faltan:
        print(f"Aviso: no se encontró el descuento {faltan} en silver_discounts; esos patrones no se aplican.")
    for k in range(N_DIAS):
        generar_dia(siguiente + timedelta(days=k), reales, sembrados, ids_descuento, gerentes)

# COMMAND ----------

if ACCION == "preparar":
    preparar()
else:
    generar()

# COMMAND ----------

# MAGIC %md
# MAGIC ### ¿El motor de riesgo detecta a los sembrados?
# MAGIC Se actualiza cuando el pipeline procesa los días nuevos. Ver también `validation/sql/fase3_simulacion.sql`.

# COMMAND ----------

if spark.catalog.tableExists(TABLA_VERDAD):
    display(spark.sql(f"""
        SELECT s.patron, s.EmployeeId, s.LocationId, s.nivel_inicial, s.score_inicial,
               r.nivel_riesgo AS nivel_actual, r.score_riesgo AS score_actual,
               round(r.veces_vs_tienda, 2) AS veces_vs_tienda, round(r.pct_efectivo, 2) AS pct_efectivo,
               round(r.pct_manager_walkout, 2) AS pct_manager_walkout, r.n_autoaprobados, r.tickets_4h_con_desc
        FROM {TABLA_VERDAD} s
        LEFT JOIN {ESQUEMA}.gold_riesgo_empleados r USING (EmployeeId, LocationId)
        ORDER BY r.score_riesgo DESC"""))
