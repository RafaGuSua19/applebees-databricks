# Calidad de datos

## Entrada a bronze

`bronze_checks` guarda cada ticket con su JSON original (`_raw_record`), archivo de origen, posición en el archivo y hora de ingesta. Si un ticket viene mal, `_rescued_data` dice por qué: archivo vacío o JSON inválido, tipo incorrecto, campos no contemplados (en cualquier nivel), llave incompleta, importes nulos o `BusinessDate` distinta a la fecha de la carpeta.

Hay dos niveles. Los **errores críticos** (`_rescued_data`) dejan el registro en Bronze y bloquean la publicación de alertas. Las **advertencias** (`_dq_warnings`: campo nuevo, artículo sin ID con precio válido, propina ausente) dejan pasar el ticket a silver y lo marcan. Tickets y detalles entran por la misma vista `valid_checks`, así que siempre salen del mismo conjunto. Como el JSON original se conserva, un campo nuevo se puede revisar e incorporar sin perder datos.

## Controles que bloquean las alertas

| Dimensión | Cómo se revisa |
|---|---|
| Estructura y tipos | Esquema explícito; registros ilegibles o con tipos incompatibles van a cuarentena |
| Campos nuevos, artículo sin ID, propina ausente | Advertencia: el ticket entra y se cuenta |
| Completitud | Mismo número de tickets, items, descuentos, pagos y voids entre bronze y silver |
| Unicidad | Llave `LocationId + dt + CheckId` sin duplicados |
| Referencias | Todo ticket tiene tienda y canal; todo empleado del score existe en el catálogo |
| Catálogos | Sin IDs nulos ni atributos contradictorios por ID |
| Conciliación | `paid = sold − disc_check + tax + tip` (±$0.05) en ≥ 95 % de los tickets con propina conocida, global y en cada día; la cobertura se reporta aparte |
| Porcentajes | `pct_desc` entre 0 y 1 y consistente con sus totales |

## Excepciones que se conservan

| Caso | Tratamiento |
|---|---|
| Ticket sin items | Se conserva (posible cancelación) y se cuenta |
| Pago negativo | Se conserva y se desglosa por `PayCatName` (reversos, venta de gift card) |
| Propina con signo invertido | Se conserva `Tip = −Gratuity` y se advierte |
| Bruto negativo o descuento mayor al bruto | Se conserva y se cuantifica para revisión |
| Horario ausente o negativo | Se cuenta; no activa la regla de 4 horas |
| Empleado nulo, 0 o fuera del catálogo | Se conserva el monto; queda fuera del score |
| `ManagerId` nulo o ≤ 0 | `sin_gerente = true`; autoaprobación solo con IDs positivos iguales |
| Líneas a $0 | Son modificadores (`es_modificador = true`); no cuentan para el mínimo de 100 líneas |

## Importes y score

Silver convierte cada importe a `DECIMAL(18,2)` antes de sumar, para evitar errores de redondeo de `double`. Las tasas de KPIs se calculan con DECIMAL(24,2) y se guardan como DECIMAL(18,9), así dan lo mismo en un refresco completo o incremental.

El score evalúa pares empleado–tienda con al menos 100 líneas con precio. La venta son las líneas que registró el empleado y el descuento lo que él aplicó, aunque sea en tickets de otra persona. La mediana se calcula entre los empleados elegibles de la misma tienda; si es cero, esa regla no suma puntos.

Los umbrales son iniciales. La regla de efectivo se activa en la mitad de los empleados porque el efectivo concentra el descuento en toda la cadena, así que es la primera que conviene calibrar con prevención de pérdidas (por ejemplo, comparar contra el % de efectivo de su propia tienda).
