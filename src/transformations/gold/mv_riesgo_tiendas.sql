-- Gold: resumen de riesgo por tienda para operaciones
CREATE MATERIALIZED VIEW gold_riesgo_tiendas
COMMENT 'Descuento por tienda, peso del efectivo y de tickets abiertos 4 h+, y empleados en riesgo'
AS WITH t AS (
  SELECT
    c.LocationId,
    COUNT(*)                                                      AS tickets,
    SUM(c.gross)                                                  AS venta_bruta,
    SUM(c.descuento)                                              AS descuento,
    SUM(CASE WHEN c.tipo_pago = 'Efectivo' THEN c.descuento ELSE 0 END) AS desc_efectivo,
    SUM(CASE WHEN c.abierto_4h THEN c.descuento ELSE 0 END)       AS desc_abiertos_4h,
    COUNT_IF(c.cien_pct_desc)                                     AS tickets_100pct_desc
  FROM silver_checks c
  GROUP BY c.LocationId
),
e AS (
  SELECT LocationId,
         COUNT_IF(nivel_riesgo = 'Alto')  AS empleados_riesgo_alto,
         COUNT_IF(nivel_riesgo = 'Medio') AS empleados_riesgo_medio
  FROM gold_riesgo_empleados
  GROUP BY LocationId
)
SELECT
  t.LocationId,
  l.Tienda,
  t.tickets,
  t.venta_bruta,
  t.descuento,
  try_divide(t.descuento, t.venta_bruta)        AS pct_desc,
  try_divide(t.desc_efectivo, t.descuento)      AS pct_desc_en_efectivo,
  try_divide(t.desc_abiertos_4h, t.descuento)   AS pct_desc_en_abiertos_4h,
  t.tickets_100pct_desc,
  coalesce(e.empleados_riesgo_alto, 0)          AS empleados_riesgo_alto,
  coalesce(e.empleados_riesgo_medio, 0)         AS empleados_riesgo_medio
FROM t
LEFT JOIN e                ON t.LocationId = e.LocationId
LEFT JOIN silver_locations l ON t.LocationId = l.LocationId;
