# Diccionario de datos — capa Gold

Este documento describe las tablas gold del proyecto de análisis de descuentos: qué representa cada fila, de dónde salen los datos y qué significa cada columna. Todas las tablas viven en `workspace.default`.

## Resumen

| Tabla | Grano (una fila por…) | Para qué se usa | Archivo |
|---|---|---|---|
| `gold_kpis_diarios` | día × tienda × canal × tipo de pago | Base del tablero de descuentos | `mv_kpis_diarios.sql` |
| `gold_riesgo_empleados` | empleado × tienda | Motor de riesgo: identifica empleados con patrones de posible abuso | `mv_riesgo_empleados.py` |
| `gold_riesgo_tiendas` | tienda | Resumen de riesgo por sucursal para operaciones | `mv_riesgo_tiendas.sql` |
| `gold_calidad_datos` | una sola fila (todo el dataset) | Monitoreo de calidad; el job la lee para decidir si continúa | `mv_calidad_datos.sql` |

### Dependencias

```
silver_checks ─┬─> gold_kpis_diarios
               ├─> gold_calidad_datos <── silver_discounts, silver_voids, silver_payments, bronze_checks
               ├─> gold_riesgo_empleados <── silver_items, silver_discounts, silver_employees
               └─> gold_riesgo_tiendas <── gold_riesgo_empleados, silver_locations
```

`gold_riesgo_tiendas` depende de `gold_riesgo_empleados`, así que esta última debe actualizarse primero.

### Convenciones

- **Llave de un ticket:** `LocationId + dt + CheckId`. `CheckId` se reinicia por tienda y por día, así que por sí solo no es único.
- **Porcentajes:** todas las columnas `pct_*` de la capa gold están expresadas como **fracción entre 0 y 1** (0.25 = 25%), no multiplicadas por 100.
- **Divisiones:** se usa `try_divide`, que devuelve **nulo** cuando el denominador es 0 (por ejemplo, un empleado sin descuentos tiene `pct_efectivo` nulo).
- **Montos:** en la moneda del sistema de punto de venta.
- **Privacidad:** ninguna tabla gold incluye `Name` ni `DateOfBirth` de empleados; solo IDs.

---

## `gold_kpis_diarios`

**Grano:** una fila por combinación de día, tienda, canal y tipo de pago.
**Fuente:** `silver_checks`, `silver_locations`, `silver_revenue_centers`.
**Uso:** base del tablero; permite filtrar y agregar por cualquiera de esas dimensiones.
**Regla de calidad:** `pct_desc` debe ser nulo o estar entre 0 y 1 (constraint `pct_desc_valido`; si no se cumple, se registra como advertencia).

| Columna | Tipo | Descripción | Cálculo |
|---|---|---|---|
| `dt` | date | Fecha de operación | — |
| `LocationId` | bigint | ID de la tienda | — |
| `Tienda` | string | Nombre de la tienda | De `silver_locations` |
| `Canal` | string | Canal de venta (In-Store, To Go, Online, Delivery…) | De `silver_revenue_centers` |
| `tipo_pago` | string | Forma de pago de los tickets: `Efectivo`, `Tarjeta crédito`, `Mixto`, `Gift card`, `App delivery`, `Otro` o `Sin pago` | — |
| `tickets` | bigint | Número de tickets | `COUNT(*)` |
| `tickets_con_desc` | bigint | Tickets con al menos un descuento | Tickets con `descuento > 0` |
| `venta_bruta` | double | Venta antes de descuentos | `SUM(gross)` |
| `descuento` | double | Monto total descontado | `SUM(descuento)` |
| `propinas` | double | Total de propinas | `SUM(tip)` |
| `tickets_100pct_desc` | bigint | Tickets descontados al 100% | Conteo de `cien_pct_desc` |
| `tickets_abiertos_4h` | bigint | Tickets abiertos 4 horas o más | Conteo de `abierto_4h` |
| `pct_desc` | double | Fracción de la venta bruta que se fue en descuentos | `descuento / venta_bruta` |

**Ojo al agregar:** para obtener `pct_desc` de una tienda o de un mes no se deben promediar los `pct_desc` diarios; hay que sumar `descuento` y `venta_bruta` y luego dividir.

---

## `gold_riesgo_empleados`

**Grano:** una fila por empleado en una tienda.
**Fuente:** `silver_items`, `silver_discounts`, `silver_checks`, `silver_employees`.
**Uso:** motor de riesgo con reglas explicables. Cada empleado se compara contra **su propia tienda**, porque cada sucursal tiene niveles normales de descuento distintos.
**Filtros:**
- Solo se cuentan líneas de venta con `GrossPrice > 0` (se excluyen modificadores como salsas o cubiertos).
- Solo se cuentan descuentos con `Amount > 0`.
- Solo se incluyen empleados con **al menos 100 líneas** de venta (`MIN_LINEAS`), para no juzgar con muestras pequeñas.

**Regla de calidad:** `score_riesgo` debe estar entre 0 y 7 (expectation `score_valido`).

### Volumen

| Columna | Tipo | Descripción | Cálculo |
|---|---|---|---|
| `EmployeeId` | bigint | ID del empleado | — |
| `LocationId` | bigint | ID de la tienda | — |
| `venta_emp` | double | Venta bruta que registró el empleado | `SUM(GrossPrice)` de sus líneas |
| `lineas` | bigint | Líneas de venta que registró | Conteo (siempre ≥ 100) |
| `desc_emp` | double | Monto total que descontó | `SUM(Amount)` de sus descuentos |
| `n_desc` | bigint | Número de descuentos que aplicó | Conteo |

### Indicadores de riesgo

| Columna | Tipo | Descripción | Cálculo |
|---|---|---|---|
| `pct_desc` | double | Fracción de su venta que descontó | `desc_emp / venta_emp` |
| `mediana_tienda` | double | Lo "normal" en su tienda: mediana de `pct_desc` de todos los empleados de esa tienda | `percentile_approx(pct_desc, 0.5)` por tienda |
| `veces_vs_tienda` | double | Cuántas veces descuenta el empleado comparado con lo normal en su tienda | `pct_desc / mediana_tienda`. **1** = igual que la mediana, **2** = el doble, **3** = el triple. Es nulo si la mediana de la tienda es 0 |
| `desc_efectivo` | double | Monto de sus descuentos aplicado en tickets pagados en efectivo | Suma de `Amount` cuando `tipo_pago = 'Efectivo'` |
| `pct_efectivo` | double | Fracción de **su monto descontado** que cayó en tickets en efectivo | `desc_efectivo / desc_emp`. Importa porque el efectivo es más fácil de tomar sin dejar rastro. No es el % de pagos en efectivo |
| `desc_manager_walkout` | double | Monto descontado con los códigos `MANAGER` (descuento discrecional del gerente) o `WALKOUT` (compensación cuando el cliente se va sin pagar). Son los códigos más fáciles de usar sin justificación | Suma de `Amount` para esos `DiscountName` |
| `pct_manager_walkout` | double | Fracción de su monto descontado que usó `MANAGER` o `WALKOUT` | `desc_manager_walkout / desc_emp` |
| `n_sin_gerente` | bigint | Descuentos sin gerente que los autorizara | Conteo de `sin_gerente` |
| `pct_sin_gerente` | double | Fracción de sus descuentos sin gerente | `n_sin_gerente / n_desc` |
| `n_autoaprobados` | bigint | Descuentos que el empleado se autorizó a sí mismo | Conteo de `autoaprobado` |
| `tickets_4h_con_desc` | bigint | Tickets distintos abiertos 4 h+ en los que aplicó descuentos | Conteo distinto de tickets con `abierto_4h` |

### Score

| Columna | Tipo | Descripción | Cálculo |
|---|---|---|---|
| `score_riesgo` | int | Puntaje de riesgo de **0 a 7**. Más alto = más señales de posible abuso | Suma de las reglas de la tabla siguiente |
| `nivel_riesgo` | string | Clasificación del score | `Alto` si score ≥ 4; `Medio` si score 2–3; `Bajo` si score 0–1 |

**Reglas del score:**

| Regla | Condición | Puntos |
|---|---|---|
| Descuenta mucho más que su tienda | `veces_vs_tienda ≥ 3` | 2 |
| | `veces_vs_tienda ≥ 2` (y < 3) | 1 |
| Descuentos concentrados en efectivo | `pct_efectivo ≥ 0.5` | 1 |
| Uso fuerte de MANAGER/WALKOUT | `pct_manager_walkout ≥ 0.3` | 1 |
| Descuentos sin autorización | `pct_sin_gerente ≥ 0.1` | 1 |
| Se autoaprueba descuentos | `n_autoaprobados > 0` | 1 |
| Descuentos en tickets abiertos mucho tiempo | `tickets_4h_con_desc ≥ 5` | 1 |
| | **Máximo posible** | **7** |

Si un indicador es nulo (por ejemplo, `veces_vs_tienda` cuando la mediana de la tienda es 0), esa regla suma 0 puntos.

**Interpretación:** el score señala a quién revisar primero, no prueba que haya abuso. Un score alto puede tener explicaciones legítimas (por ejemplo, un gerente que aplica más descuentos por su rol).

### Antigüedad

| Columna | Tipo | Descripción | Cálculo |
|---|---|---|---|
| `HireDate` | string | Fecha de contratación, como texto tal cual viene del catálogo de empleados | De `silver_employees` |
| `anios_antiguedad` | bigint | Años completos de antigüedad a la fecha de corte | `floor(días entre HireDate y la fecha máxima de los datos / 365)`. Nulo si no hay `HireDate` |

---

## `gold_riesgo_tiendas`

**Grano:** una fila por tienda.
**Fuente:** `silver_checks`, `gold_riesgo_empleados`, `silver_locations`.
**Uso:** resumen para operaciones; permite priorizar qué sucursales auditar.

| Columna | Tipo | Descripción | Cálculo |
|---|---|---|---|
| `LocationId` | bigint | ID de la tienda | — |
| `Tienda` | string | Nombre de la tienda | De `silver_locations` |
| `tickets` | bigint | Número de tickets | `COUNT(*)` |
| `venta_bruta` | double | Venta antes de descuentos | `SUM(gross)` |
| `descuento` | double | Monto total descontado | `SUM(descuento)` |
| `pct_desc` | double | Fracción de la venta que se fue en descuentos | `descuento / venta_bruta` |
| `pct_desc_en_efectivo` | double | Fracción del descuento de la tienda que cayó en tickets en efectivo | Descuento en tickets `Efectivo` / `descuento` |
| `pct_desc_en_abiertos_4h` | double | Fracción del descuento de la tienda que cayó en tickets abiertos 4 h+ | Descuento en tickets `abierto_4h` / `descuento` |
| `tickets_100pct_desc` | bigint | Tickets descontados al 100% | Conteo de `cien_pct_desc` |
| `empleados_riesgo_alto` | bigint | Empleados de la tienda con `nivel_riesgo = 'Alto'` | De `gold_riesgo_empleados`; 0 si no hay |
| `empleados_riesgo_medio` | bigint | Empleados de la tienda con `nivel_riesgo = 'Medio'` | De `gold_riesgo_empleados`; 0 si no hay |

Los conteos de empleados solo consideran a quienes pasaron el filtro de 100 líneas en `gold_riesgo_empleados`.

---

## `gold_calidad_datos`

**Grano:** una sola fila con métricas del dataset completo.
**Fuente:** `silver_checks`, `silver_discounts`, `silver_voids`, `silver_payments`, `bronze_checks`.
**Uso:** tablero de calidad. El job la lee para decidir si el pipeline continúa o se detiene.

| Columna | Tipo | Descripción | Valor esperado |
|---|---|---|---|
| `tickets` | bigint | Total de tickets | — |
| `dias` | bigint | Días distintos con datos | — |
| `tiendas` | bigint | Tiendas distintas con datos | — |
| `llaves_duplicadas` | bigint | Combinaciones `LocationId + dt + CheckId` que aparecen más de una vez | 0 |
| `pct_tickets_conciliados` | double | Fracción de tickets donde el pago cuadra con `sold − disc_check + tax + tip`, con tolerancia de ±0.05 | Cercano a 1 |
| `tickets_sin_items` | bigint | Tickets sin productos | Bajo |
| `tickets_horario_invalido` | bigint | Tickets sin duración calculable o con cierre antes de la apertura (`min_abierto` nulo o negativo) | 0 |
| `descuentos_monto_cero` | bigint | Registros de descuento con monto $0 | Informativo (se excluyen del análisis de riesgo) |
| `descuentos_negativos` | bigint | Registros de descuento con monto negativo | 0 |
| `voids_monto_cero` | bigint | Anulaciones con monto $0 | Informativo |
| `propinas_con_signo_invertido` | bigint | Pagos con propina negativa después de corregir el signo de `Gratuity` | 0 o muy bajo |
| `registros_rescatados` | bigint | Archivos diarios de tickets que no se pudieron leer con el formato esperado. Cada uno deja una fila en `bronze_checks` con `_rescued_data` no nulo | 0 |
| `calculado_en` | timestamp | Momento en que se calcularon las métricas | — |
