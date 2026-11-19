"""Reglas para generar tickets de días nuevos a partir de un día real y sembrar casos de abuso.

No usa Spark para poder probarse localmente (tests/unit/test_simulacion.py).
"""
import random
from datetime import date, datetime, timedelta
from decimal import Decimal

CENTAVO = Decimal("0.01")

# Cada patrón combina señales distintas. El patrón sutil sirve para medir sensibilidad en tarjeta.
# frecuencia multiplica tickets_por_empleado: 1.0 son ~15 tickets al día.
PATRONES = {
    "efectivo_manager":    dict(descuento="MANAGER", pct=(0.50, 0.90), efectivo=True,  gerente="otro",    horas=None, frecuencia=1.0),
    "walkout_sin_gerente": dict(descuento="WALKOUT", pct=(0.60, 0.90), efectivo=True,  gerente="ninguno", horas=None, frecuencia=1.0),
    "autoaprobado_4h":     dict(descuento="MANAGER", pct=(0.40, 0.80), efectivo=True,  gerente="mismo",   horas=(4.2, 6.0), frecuencia=1.0),
    "sutil":               dict(descuento="MANAGER", pct=(0.15, 0.30), efectivo=False, gerente="otro",    horas=None, frecuencia=1.0),
}

# Cohorte de prueba: patrones que no se usaron para calibrar los umbrales de la v2.
#   goteo_manager       -> pocos MANAGER al día, cerca del umbral semanal de la v2.
#   walkout_tarjeta     -> WALKOUT sin gerente pagado con tarjeta, también poco frecuente.
#   error_servidor      -> el abuso se esconde en un código de error (SERVERERR), no en MANAGER/WALKOUT.
#   emp50_clientes      -> descuento de empleado al 50 % aplicado a clientes con tarjeta.
PATRONES_PRUEBA = {
    "goteo_manager":   dict(descuento="MANAGER",   pct=(0.35, 0.60), efectivo=True,  gerente="otro",    horas=None, frecuencia=0.15),
    "walkout_tarjeta": dict(descuento="WALKOUT",   pct=(0.50, 0.80), efectivo=False, gerente="ninguno", horas=None, frecuencia=0.20),
    "error_servidor":  dict(descuento="SERVERERR", pct=(0.40, 0.70), efectivo=True,  gerente="otro",    horas=None, frecuencia=0.70),
    "emp50_clientes":  dict(descuento="EMP 50",    pct=(0.50, 0.50), efectivo=False, gerente="otro",    horas=None, frecuencia=0.50),
}

COHORTES = {"base": PATRONES, "prueba": PATRONES_PRUEBA}
TODOS_LOS_PATRONES = {**PATRONES, **PATRONES_PRUEBA}


def descuentos_requeridos():
    return sorted({p["descuento"] for p in TODOS_LOS_PATRONES.values()})

CAMPOS_FECHA = ("BusinessDate", "OpenTime", "CloseTime")


def _dec(valor):
    return Decimal(str(valor or 0))


def _monto(valor):
    return float(Decimal(valor).quantize(CENTAVO))


def rng_para(*partes):
    """Generador reproducible: la misma semilla y llaves dan siempre el mismo resultado."""
    return random.Random("|".join(str(p) for p in partes))


def mover_fecha(valor, dias):
    """Recorre la parte YYYY-MM-DD de un texto ISO; el resto (hora, zona) queda igual."""
    if not isinstance(valor, str) or len(valor) < 10:
        return valor
    try:
        fecha = date.fromisoformat(valor[:10])
    except ValueError:
        return valor
    return (fecha + timedelta(days=dias)).isoformat() + valor[10:]


def mover_ticket(t, dias):
    for campo in CAMPOS_FECHA:
        if campo in t:
            t[campo] = mover_fecha(t[campo], dias)
    for item in t.get("ItemsSold") or []:
        if "OrderTime" in item:
            item["OrderTime"] = mover_fecha(item["OrderTime"], dias)
    return t


def base_descontable(t):
    """Venta después de descuentos de item y de ticket (lo que todavía se puede descontar)."""
    vendido = sum(_dec(i.get("SoldPrice")) for i in t.get("ItemsSold") or [])
    previo = sum(_dec(d.get("Amount")) for d in t.get("Discounts") or [])
    return vendido - previo


def tiene_venta(t):
    return any(_dec(i.get("GrossPrice")) > 0 for i in t.get("ItemsSold") or [])


def asignar_empleado(t, empleado):
    """El ticket pasa a ser atendido por el empleado sembrado (items y pagos)."""
    for item in t.get("ItemsSold") or []:
        item["EmployeeId"] = empleado
    for pago in t.get("Payments") or []:
        pago["EmployeeId"] = empleado
    return t


def _alargar(t, rng, horas):
    try:
        apertura = datetime.fromisoformat(t["OpenTime"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError):
        return
    cierre = apertura + timedelta(hours=rng.uniform(*horas))
    # Mismo formato que la fuente: la mayoría viene como AAAA-MM-DDTHH:MM, sin segundos.
    if len(t["OpenTime"]) == 16:
        t["CloseTime"] = cierre.strftime("%Y-%m-%dT%H:%M")
        return
    texto = cierre.isoformat()
    if t["OpenTime"].endswith("Z") and texto.endswith("+00:00"):
        texto = texto[:-6] + "Z"
    t["CloseTime"] = texto


def aplicar_abuso(t, empleado, patron, plantilla_efectivo, ids_descuento, gerente_tienda, rng):
    """Agrega un descuento de ticket con el patrón indicado y ajusta impuestos y pagos para que
    el ticket siga conciliando: paid = sold - disc_check + tax + tip.
    Regresa el monto sembrado o None si el ticket no se puede usar."""
    p = TODOS_LOS_PATRONES[patron]
    base = base_descontable(t)
    if base < 10 or p["descuento"] not in ids_descuento:
        return None
    pagos = t.get("Payments") or []
    plantilla = plantilla_efectivo if p["efectivo"] else next((x for x in pagos if x.get("IsCreditCard")), None)
    if not plantilla or (p["gerente"] == "otro" and not gerente_tienda):
        return None

    asignar_empleado(t, empleado)
    monto = (base * Decimal(str(rng.uniform(*p["pct"])))).quantize(CENTAVO)
    gerente = {"otro": gerente_tienda or 0, "ninguno": 0, "mismo": empleado}[p["gerente"]]
    nombre, id_desc = ids_descuento[p["descuento"]]
    t["Discounts"] = (t.get("Discounts") or []) + [{
        "Amount": _monto(monto), "DiscountId": id_desc, "DiscountName": nombre,
        "EmployeeId": empleado, "ManagerId": gerente,
    }]

    # El impuesto baja en la misma proporción que la venta neta.
    neto = base - monto
    for impuesto in t.get("Tax") or []:
        impuesto["Amount"] = _monto(_dec(impuesto.get("Amount")) * neto / base)
    impuestos = sum(_dec(i.get("Amount")) for i in t.get("Tax") or [])
    propina = -sum(_dec(x.get("Gratuity")) for x in pagos)
    total = neto + impuestos + propina
    pago = dict(plantilla, Amount=_monto(total), Gratuity=_monto(-propina), EmployeeId=empleado)
    t["Payments"] = [pago]

    if p["horas"]:
        _alargar(t, rng, p["horas"])
    return monto


def asignar_patrones(empleados, cohorte="base"):
    """Reparte los patrones de la cohorte en orden entre los empleados elegidos (ya barajados)."""
    nombres = list(COHORTES[cohorte])
    return [(emp, loc, nombres[i % len(nombres)]) for i, (emp, loc) in enumerate(empleados)]


def probabilidad_siembra(patron, tickets_por_empleado, tickets_tienda):
    """Probabilidad de que un ticket de la tienda se use para sembrar abuso ese día."""
    return tickets_por_empleado * TODOS_LOS_PATRONES[patron]["frecuencia"] / max(tickets_tienda, 1)


def elegir_empleados(candidatos, n, rng, excluir_tiendas=()):
    """candidatos: lista de (EmployeeId, LocationId). Uno por tienda para no mezclar señales.
    excluir_tiendas deja fuera las tiendas de cohortes anteriores."""
    candidatos = sorted(candidatos)
    rng.shuffle(candidatos)
    elegidos, tiendas, empleados = [], set(excluir_tiendas), set()
    for emp, loc in candidatos:
        if loc not in tiendas and emp not in empleados:
            elegidos.append((emp, loc))
            tiendas.add(loc)
            empleados.add(emp)
        if len(elegidos) == n:
            break
    return elegidos
