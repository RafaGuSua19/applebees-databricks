-- Gold: tablero de calidad de datos (lo lee el job para decidir si continúa)
CREATE MATERIALIZED VIEW gold_calidad_datos
COMMENT 'Métricas de calidad: unicidad, conciliación, completitud y validez'
AS WITH k AS (
  SELECT LocationId, dt, CheckId, COUNT(*) AS n
  FROM silver_checks
  GROUP BY LocationId, dt, CheckId
)
SELECT
  (SELECT COUNT(*) FROM silver_checks)                                    AS tickets,
  (SELECT COUNT(DISTINCT dt) FROM silver_checks)                          AS dias,
  (SELECT COUNT(DISTINCT LocationId) FROM silver_checks)                  AS tiendas,
  (SELECT COUNT(*) FROM k WHERE n > 1)                                    AS llaves_duplicadas,
  (SELECT AVG(CASE WHEN abs(paid - (sold - disc_check + tax + tip)) <= 0.05 THEN 1.0 ELSE 0.0 END)
     FROM silver_checks)                                                  AS pct_tickets_conciliados,
  (SELECT COUNT_IF(n_items = 0) FROM silver_checks)                       AS tickets_sin_items,
  (SELECT COUNT_IF(min_abierto IS NULL OR min_abierto < 0) FROM silver_checks) AS tickets_horario_invalido,
  (SELECT COUNT_IF(Amount = 0) FROM silver_discounts)                     AS descuentos_monto_cero,
  (SELECT COUNT_IF(Amount < 0) FROM silver_discounts)                     AS descuentos_negativos,
  (SELECT COUNT_IF(Amount = 0) FROM silver_voids)                         AS voids_monto_cero,
  (SELECT COUNT_IF(Tip < 0) FROM silver_payments)                         AS propinas_con_signo_invertido,
  (SELECT COUNT_IF(_rescued_data IS NOT NULL) FROM bronze_checks)         AS registros_rescatados,
  current_timestamp()                                                     AS calculado_en;
