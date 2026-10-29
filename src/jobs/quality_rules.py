"""Reglas de publicación sin dependencias Spark; compartidas por el job y las pruebas."""
import math
import re
from numbers import Number

ZERO_REQUIRED = (
    "llaves_duplicadas", "registros_rescatados", "diferencia_tickets",
    "diferencia_items", "diferencia_descuentos", "diferencia_pagos", "diferencia_voids",
    "tickets_sin_tienda", "tickets_sin_canal", "dimensiones_invalidas",
    "identidades_invalidas_en_riesgo", "kpis_pct_invalidos", "kpis_tasa_inconsistente",
)


def qualified_schema(catalog, schema):
    for value in (catalog, schema):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError(f"Identificador de catálogo/esquema inválido: {value!r}")
    return f"{catalog}.{schema}"


def quality_errors(rows, min_reconciled=0.95):
    """Devuelve todos los fallos críticos; una métrica ausente jamás se acepta."""
    if len(rows) != 1:
        return [f"se esperaba una fila de calidad; llegaron {len(rows)}"]
    if not 0 <= min_reconciled <= 1:
        raise ValueError("El umbral de conciliación debe estar entre 0 y 1")
    dq = rows[0]
    errors = []
    for key in ("tickets", *ZERO_REQUIRED, "pct_tickets_conciliados", "min_pct_conciliado_diario"):
        value = dq.get(key)
        if isinstance(value, bool) or not isinstance(value, Number) or not math.isfinite(value):
            errors.append(f"métrica {key} ausente, nula o no finita")
            continue
        if key in ("pct_tickets_conciliados", "min_pct_conciliado_diario"):
            if not 0 <= value <= 1 or value < min_reconciled:
                errors.append(f"{key}={value:.4%}; mínimo {min_reconciled:.0%}, máximo 100%")
        elif value < 0 or value != int(value):
            errors.append(f"contador {key} inválido: {value}")
        elif key == "tickets" and value == 0:
            errors.append("no hay tickets en silver_checks")
        elif key in ZERO_REQUIRED and value != 0:
            errors.append(f"{key}={value}; se requiere cero")
    return errors
