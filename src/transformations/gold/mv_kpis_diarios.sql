-- Gold: KPIs diarios de descuento por tienda, canal y tipo de pago (base del tablero)
CREATE MATERIALIZED VIEW gold_kpis_diarios (
  CONSTRAINT pct_desc_valido EXPECT (pct_desc IS NULL OR pct_desc BETWEEN 0 AND 1)
)
CLUSTER BY (dt, LocationId)
COMMENT 'KPIs diarios de descuento por tienda, canal y tipo de pago'
AS SELECT
  c.dt,
  c.LocationId,
  l.Tienda,
  rc.Canal,
  c.tipo_pago,
  COUNT(*)                              AS tickets,
  COUNT_IF(c.descuento > 0)             AS tickets_con_desc,
  SUM(c.gross)                          AS venta_bruta,
  SUM(c.descuento)                      AS descuento,
  SUM(c.tip)                            AS propinas,
  COUNT_IF(c.cien_pct_desc)             AS tickets_100pct_desc,
  COUNT_IF(c.abierto_4h)                AS tickets_abiertos_4h,
  -- Fijar tipos antes y después de dividir: el plan incremental puede ensanchar
  -- SUM a DECIMAL(38,2) y reducir la escala de la división si queda implícita.
  CAST(try_divide(CAST(SUM(c.descuento) AS DECIMAL(24,2)),
                  CAST(SUM(c.gross) AS DECIMAL(24,2))) AS DECIMAL(18,9)) AS pct_desc
FROM silver_checks c
LEFT JOIN silver_locations l        ON c.LocationId = l.LocationId
LEFT JOIN silver_revenue_centers rc ON c.CheckRevenueCenterId = rc.CheckRevenueCenterId
GROUP BY ALL;
