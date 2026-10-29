# Contrato de datos y decisiones de calidad

## Admisión y conservación

`bronze_checks` conserva `_raw_record` (objeto JSON), `_source_file`, `_record_index`, `_ingested_at`, fecha y marca. Un archivo vacío o inválido produce un diagnóstico recuperable. La interpretación por ticket detecta campos adicionales incluso en arrays anidados, tipos incompatibles, llaves ausentes, importes esenciales nulos y discordancia entre `BusinessDate` y la fecha del path. `_rescued_data` guarda el motivo, no un fragmento truncado que sustituya al original.

La vista `valid_checks` es la única entrada de los tickets y de todos sus detalles en silver. Los registros con diagnóstico permanecen en bronze; no generan detalles huérfanos. La compuerta bloquea las alertas si existe cualquier registro rescatado. El JSON original permite inspeccionar campos nuevos y corregir el contrato sin perderlos silenciosamente.

Los arrays de actividad nulos o vacíos representan ausencia de movimientos, como en la fuente original. Un elemento presente con importe esencial nulo es inválido. La validación no implica que todo string opcional tenga significado de negocio: horarios, empleados desconocidos y signos se controlan además en silver/gold.

## Controles críticos

| Dimensión | Implementación | Acción |
|---|---|---|
| Estructura/tipos | Parser con esquema explícito, columna de corrupción y detección recursiva de campos extra | Conservar en bronze, excluir el ticket completo de silver, bloquear alertas |
| Completitud | Conteos de tickets, items, descuentos, pagos y voids válidos esperados desde bronze contra silver | Bloquear si difieren |
| Unicidad | Llave `LocationId + dt + CheckId` | Bloquear duplicados; no elegir arbitrariamente una copia |
| Referencias | Ticket debe enlazar tienda y canal; score debe enlazar un empleado positivo | Bloquear referencias perdidas |
| Catálogos | IDs obligatorios y ausencia de atributos contradictorios por ID | Bloquear contradicciones; duplicados idénticos se consolidan |
| Consistencia monetaria | `paid = sold - disc_check + tax + tip`, tolerancia $0.05 | Conciliación ≥95% global y en cada día |
| Porcentajes | `pct_desc` gold entre 0 y 1, o nulo cuando venta bruta es cero; igualdad con el cociente de sus totales a nueve decimales | Bloquear resultados fuera del contrato |
| Métricas | Exactamente una fila de calidad, contadores enteros no negativos, ratios finitos | Bloquear nulos, ausencias, infinitos y cardinalidad incorrecta |

La compuerta valida publicación para alertas; no proporciona una transacción atómica de todas las tablas del pipeline. Un consumidor debe comprobar el éxito de la corrida completa. El 95% es un umbral inicial explícito, no una garantía de exactitud de cada ticket; se reportan también los errores absolutos y el peor día.

## Excepciones conservadas y monitorizadas

| Caso | Tratamiento y motivo |
|---|---|
| Ticket sin items | Conservar; puede representar una cancelación o actividad sin venta. Contar `tickets_sin_items`. |
| Importe negativo en pagos | Conservar y desglosar por `PayCatName`. Puede ser reverso o venta de gift card; confirmar semántica con negocio. |
| Propina con signo invertido | Conservar `Tip=-Gratuity` y advertir. No recortar a cero ni alterar conciliación. |
| Bruto negativo, descuentos negativos o mayores al bruto | Conservar y cuantificar. Revisión de operaciones; no ocultar al calcular el riesgo. |
| Horario ausente/negativo | Advertir y contar. Duración nula no activa la regla de cuatro horas. |
| EmployeeId nulo, cero o fuera del catálogo | Mantener movimiento monetario y contarlo; excluir identidad del score. |
| ManagerId nulo o no positivo | `sin_gerente=true`. Autoaprobación solo cuando ambos IDs son positivos e iguales. |
| Modificadores a $0 | Conservar; `es_modificador=true`. El denominador de elegibilidad usa líneas con precio positivo. |

## Política monetaria y límites del score

Silver convierte cada importe a `DECIMAL(18,2)` antes de agregar. Spark redondea al centavo al convertir; los datos de referencia usan importes de dos decimales. La tasa de KPIs convierte los totales a DECIMAL(24,2) antes de dividir y el resultado a DECIMAL(18,9), para conservar la misma precisión en refrescos completos e incrementales. Las tasas usan división segura y no se recortan a [0,1] para ocultar errores. La conciliación usa una tolerancia de cinco centavos independiente del redondeo visual.

El score 0–7 evalúa pares empleado–tienda identificados con ≥100 líneas de precio positivo. Su venta son las líneas registradas por ese empleado; sus descuentos son los que aplicó, incluso a tickets vendidos por otra persona. Por tanto, esa atribución es una señal operativa y no una cuenta de rentabilidad individual. La mediana se calcula entre empleados elegibles de la misma tienda. Si es cero, el ratio queda nulo y la regla comparativa no suma puntos.

Los umbrales son iniciales. La señal de efectivo puede ser frecuente en toda la cadena; calibrar contra una muestra revisada antes de tratar el score como clasificación de abuso. Preservar distinción entre conteo de IDs, pares empleado–tienda y movimientos de descuento. No extrapolar descuentos asociados al score a dinero recuperable.
