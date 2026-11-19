"""Reglas para generar tickets de días nuevos a partir de un día real y sembrar casos de abuso.

No usa Spark para poder probarse localmente (tests/unit/test_simulacion.py).
"""
import random
from datetime import date, datetime, timedelta
from decimal import Decimal

CENTAVO = Decimal("0.01")

# Cada patrón combina señales distintas. El patrón sutil sirve para medir sensibilidad en tarjeta.
PATRONES = {
    "efectivo_manager":    dict(descuento="MANAGER", pct=(0.50, 0.90), efectivo=True,  gerente="otro",    horas=None),
    "walkout_sin_gerente": dict(descuento="WALKOUT", pct=(0.60, 0.90), efectivo=True,  gerente="ninguno", horas=None),
    "autoaprobado_4h":     dict(descuento="MANAGER", pct=(0.40, 0.80), efectivo=True,  gerente="mismo",   horas=(4.2, 6.0)),
    "sutil":               dict(descuento="MANAGER", pct=(0.15, 0.30), efectivo=False, gerente="otro",    horas=None),
}

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
    p = PATRONES[patron]
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


def asignar_patrones(empleados):
    """Reparte los patrones en orden entre los empleados elegidos (ya barajados)."""
    nombres = list(PATRONES)
    return [(emp, loc, nombres[i % len(nombres)]) for i, (emp, loc) in enumerate(empleados)]


def elegir_empleados(candidatos, n, rng):
    """candidatos: lista de (EmployeeId, LocationId). Uno por tienda para no mezclar señales."""
    candidatos = sorted(candidatos)
    rng.shuffle(candidatos)
    elegidos, tiendas = [], set()
    for emp, loc in candidatos:
        if loc not in tiendas:
            elegidos.append((emp, loc))
            tiendas.add(loc)
        if len(elegidos) == n:
            break
    return elegidos
