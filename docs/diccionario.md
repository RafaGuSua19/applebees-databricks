# Diccionario de tablas

Esta es la referencia de grano y propósito de todas las capas. El [diccionario de datos Gold](diccionario_datos.md) detalla cada columna y sus reglas.

Todas las tablas viven en el catálogo y esquema definidos por el target. Los nombres siguientes son relativos a ese esquema. `dt` es DATE; IDs son BIGINT; importes base de silver se convierten a DECIMAL(18,2); la aritmética derivada y las agregaciones monetarias amplían precisión. Las tasas son proporciones, no porcentajes multiplicados por 100.

| Tabla | Tipo | Grano / llave lógica | Campos y propósito |
|---|---|---|---|
| `bronze_checks` | Streaming table | Ticket o diagnóstico; origen + ordinal | Estructura anidada original, `_raw_record`, `_rescued_data`, `_source_file`, `_record_index`, `dt`, `brand`, `_ingested_at` |
| `bronze_locations` | Materialized view | Registro de catálogo | Fuente de tiendas, fechas y zona horaria |
| `bronze_revenue_centers` | Materialized view | Registro de catálogo | Fuente de canales |
| `bronze_employees` | Materialized view | Registro de catálogo | Fuente de identidad/contratación; contiene datos personales de acceso restringido |
| `bronze_items` | Materialized view | Registro de catálogo | Catálogo de menú para trazabilidad y análisis posterior; los tickets ya llevan atributos del item |
| `silver_checks` | Streaming table | `LocationId + dt + CheckId` | `gross`, `sold`, `disc_item`, `disc_check`, `descuento`, `venta_neta`, `tax`, `paid`, `tip`, `tipo_pago`, `min_abierto`, `cien_pct_desc`, `abierto_4h` |
| `silver_items` | Streaming table | Línea de item en ticket | ID, empleado, bruto/neto, cantidad, secuencia y `es_modificador` |
| `silver_discounts` | Streaming table | Movimiento de descuento en ticket/item | `Nivel`, `Amount`, `DiscountName`, `categoria`, `EmployeeId`, `ManagerId`, `sin_gerente`, `autoaprobado` |
| `silver_payments` | Streaming table | Movimiento de pago en ticket | `Amount`, `Gratuity`, `Tip`, `PayCatName`, banderas del medio |
| `silver_voids` | Streaming table | Movimiento de anulación | `Amount`, item, empleado, gerente y motivo |
| `silver_locations` | Materialized view | `LocationId` | `Tienda`, apertura, cierre y zona horaria |
| `silver_revenue_centers` | Materialized view | `CheckRevenueCenterId` | `Canal` |
| `silver_employees` | Materialized view | `EmployeeId` | `HireDate`, `PrimaryJobID`; excluye nombre, nacimiento y minoría de edad |
| `gold_kpis_diarios` | Materialized view | `dt + LocationId + Canal + tipo_pago` | Tickets, venta, descuento, propinas, tickets 100%, tickets 4h y `pct_desc` |
| `gold_riesgo_empleados` | Materialized view | `EmployeeId + LocationId` | Venta/descuento atribuidos, mediana, ratios, conteos de señales, antigüedad, `score_riesgo`, `nivel_riesgo` |
| `gold_riesgo_tiendas` | Materialized view | `LocationId` | Venta, descuento, peso de efectivo/4h, tickets 100%, empleados Alto/Medio |
| `gold_calidad_datos` | Materialized view | Una fila por estado actualizado del dataset | Contadores críticos y de observación, conciliación global/diaria, `fecha_corte`, `calculado_en` |

Además, `valid_checks` es una vista interna del pipeline: selecciona tickets sin diagnóstico estructural. No añade una tabla de negocio ni un cuarto nivel de arquitectura.

`cien_pct_desc` significa bruto positivo y neto ≤$0.01; incluye los casos excepcionales con neto negativo, que se cuentan por separado como exceso de descuento. `abierto_4h` es duración ≥240 minutos. `sin_gerente` incluye nulo y no positivo. `autoaprobado` exige IDs positivos coincidentes. Una fila de detalle no es única por la llave del ticket; varias líneas y movimientos legítimos comparten esa llave.

Los catálogos se leen como snapshots JSON. Las dimensiones silver consolidan IDs, mientras el contrato de calidad detecta atributos contradictorios antes de que esos resultados se utilicen en alertas. No se modela historia SCD porque la fuente entregada solo contiene un snapshot.
