-- Un único contrato de publicación, con excepciones de negocio visibles.
CREATE MATERIALIZED VIEW gold_calidad_datos
COMMENT 'Completitud entre capas, unicidad, validez, integridad referencial y excepciones conservadas'
AS WITH k AS (
  SELECT LocationId, dt, CheckId, COUNT(*) AS n FROM silver_checks GROUP BY ALL
), diario AS (
  SELECT dt, AVG(CASE WHEN abs(paid - (sold - disc_check + tax + tip)) <= 0.05 THEN 1.0 ELSE 0.0 END) AS pct
  FROM silver_checks GROUP BY dt
), entrada AS (
  SELECT COUNT(*) AS tickets,
    SUM(coalesce(array_size(ItemsSold), 0)) AS items,
    SUM(coalesce(array_size(Discounts), 0) + coalesce(aggregate(ItemsSold, 0,
      (a, i) -> a + coalesce(array_size(i.Discounts), 0)), 0)) AS descuentos,
    SUM(coalesce(array_size(Payments), 0)) AS pagos,
    SUM(coalesce(array_size(Voids), 0)) AS voids
  FROM bronze_checks WHERE _rescued_data IS NULL
), dims_invalidas AS (
  SELECT COUNT(*) AS n FROM (
    SELECT Id FROM bronze_locations GROUP BY Id
      HAVING Id IS NULL OR COUNT(DISTINCT struct(Name, OpenDate, ClosedDate, TimeZoneName)) > 1
    UNION ALL
    SELECT Id FROM bronze_revenue_centers GROUP BY Id
      HAVING Id IS NULL OR COUNT(DISTINCT Name) > 1
    UNION ALL
    SELECT Id FROM bronze_employees GROUP BY Id
      HAVING Id IS NULL OR Id <= 0 OR COUNT(DISTINCT struct(HireDate, PrimaryJobID)) > 1
  )
)
SELECT
  (SELECT COUNT(*) FROM silver_checks) AS tickets,
  (SELECT COUNT(DISTINCT dt) FROM silver_checks) AS dias,
  (SELECT COUNT(DISTINCT LocationId) FROM silver_checks) AS tiendas,
  (SELECT COUNT(DISTINCT _source_file) FROM bronze_checks) AS archivos,
  (SELECT COUNT(*) FROM k WHERE n > 1) AS llaves_duplicadas,
  (SELECT AVG(CASE WHEN abs(paid - (sold - disc_check + tax + tip)) <= 0.05 THEN 1.0 ELSE 0.0 END)
     FROM silver_checks) AS pct_tickets_conciliados,
  (SELECT MIN(pct) FROM diario) AS min_pct_conciliado_diario,
  (SELECT COUNT_IF(_rescued_data IS NOT NULL) FROM bronze_checks) AS registros_rescatados,
  abs((SELECT tickets FROM entrada) - (SELECT COUNT(*) FROM silver_checks)) AS diferencia_tickets,
  abs((SELECT items FROM entrada) - (SELECT COUNT(*) FROM silver_items)) AS diferencia_items,
  abs((SELECT descuentos FROM entrada) - (SELECT COUNT(*) FROM silver_discounts)) AS diferencia_descuentos,
  abs((SELECT pagos FROM entrada) - (SELECT COUNT(*) FROM silver_payments)) AS diferencia_pagos,
  abs((SELECT voids FROM entrada) - (SELECT COUNT(*) FROM silver_voids)) AS diferencia_voids,
  (SELECT COUNT(*) FROM silver_checks c LEFT ANTI JOIN silver_locations l ON c.LocationId = l.LocationId) AS tickets_sin_tienda,
  (SELECT COUNT(*) FROM silver_checks c LEFT ANTI JOIN silver_revenue_centers r ON c.CheckRevenueCenterId = r.CheckRevenueCenterId) AS tickets_sin_canal,
  (SELECT n FROM dims_invalidas) AS dimensiones_invalidas,
  (SELECT COUNT(*) FROM gold_riesgo_empleados r LEFT ANTI JOIN silver_employees e
    ON r.EmployeeId = e.EmployeeId AND e.EmployeeId > 0) AS identidades_invalidas_en_riesgo,
  (SELECT COUNT_IF(pct_desc IS NOT NULL AND NOT (pct_desc BETWEEN 0 AND 1)) FROM gold_kpis_diarios) AS kpis_pct_invalidos,
  (SELECT COUNT_IF(NOT (pct_desc <=> CAST(try_divide(CAST(descuento AS DECIMAL(24,2)),
      CAST(venta_bruta AS DECIMAL(24,2))) AS DECIMAL(18,9)))) FROM gold_kpis_diarios) AS kpis_tasa_inconsistente,
  (SELECT COUNT_IF(n_items = 0) FROM silver_checks) AS tickets_sin_items,
  (SELECT COUNT_IF(min_abierto IS NULL OR min_abierto < 0) FROM silver_checks) AS tickets_horario_invalido,
  (SELECT COUNT_IF(descuento > gross + 0.05) FROM silver_checks) AS tickets_descuento_supera_bruto,
  (SELECT COUNT_IF(abs(gross - sold - disc_item) > 0.05) FROM silver_checks) AS tickets_items_no_conciliados,
  (SELECT COUNT_IF(GrossPrice < 0) FROM silver_items) AS items_bruto_negativo,
  (SELECT COUNT_IF(Amount = 0) FROM silver_discounts) AS descuentos_monto_cero,
  (SELECT COUNT_IF(Amount < 0) FROM silver_discounts) AS descuentos_negativos,
  (SELECT COUNT(*) FROM silver_discounts d LEFT ANTI JOIN silver_employees e
    ON d.EmployeeId = e.EmployeeId AND e.EmployeeId > 0) AS descuentos_identidad_desconocida,
  (SELECT COUNT_IF(Amount = 0) FROM silver_voids) AS voids_monto_cero,
  (SELECT COUNT_IF(Amount < 0) FROM silver_payments) AS pagos_negativos,
  (SELECT COUNT_IF(Tip < 0) FROM silver_payments) AS propinas_con_signo_invertido,
  (SELECT MAX(dt) FROM silver_checks) AS fecha_corte,
  current_timestamp() AS calculado_en;
