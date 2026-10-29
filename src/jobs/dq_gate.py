# Databricks notebook source
# Compuerta de calidad: si alguna regla crítica falla, el job se detiene y avisa por correo.
ESQUEMA = "workspace.applebees"
MIN_CONCILIADOS = 0.95

dq = spark.table(f"{ESQUEMA}.gold_calidad_datos").collect()[0].asDict()
for k, v in dq.items():
    print(f"{k}: {v}")

errores = []
if dq["tickets"] == 0:
    errores.append("no hay tickets en silver_checks")
if dq["llaves_duplicadas"] > 0:
    errores.append(f"{dq['llaves_duplicadas']} llaves de ticket duplicadas")
if dq["pct_tickets_conciliados"] < MIN_CONCILIADOS:
    errores.append(f"solo {dq['pct_tickets_conciliados']:.2%} de tickets concilian (mínimo {MIN_CONCILIADOS:.0%})")
if dq["registros_rescatados"] > 0:
    errores.append(f"{dq['registros_rescatados']} registros con esquema inesperado (_rescued_data)")

if errores:
    raise Exception("Falló la compuerta de calidad: " + "; ".join(errores))
print("Calidad OK: el job continúa.")
