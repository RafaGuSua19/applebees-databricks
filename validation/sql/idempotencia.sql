-- Huella multiconjunto de contenido: comparar antes/después de una corrida sin nuevas entradas.
SELECT 'bronze_checks' AS tabla, COUNT(*) AS filas, SUM(CAST(xxhash64(struct(*)) AS DECIMAL(38,0))) AS huella FROM bronze_checks
UNION ALL
SELECT 'silver_checks' AS tabla, COUNT(*) AS filas, SUM(CAST(xxhash64(struct(*)) AS DECIMAL(38,0))) AS huella FROM silver_checks
UNION ALL
SELECT 'silver_items' AS tabla, COUNT(*) AS filas, SUM(CAST(xxhash64(struct(*)) AS DECIMAL(38,0))) AS huella FROM silver_items
UNION ALL
SELECT 'silver_discounts' AS tabla, COUNT(*) AS filas, SUM(CAST(xxhash64(struct(*)) AS DECIMAL(38,0))) AS huella FROM silver_discounts
UNION ALL
SELECT 'silver_payments' AS tabla, COUNT(*) AS filas, SUM(CAST(xxhash64(struct(*)) AS DECIMAL(38,0))) AS huella FROM silver_payments
UNION ALL
SELECT 'silver_voids' AS tabla, COUNT(*) AS filas, SUM(CAST(xxhash64(struct(*)) AS DECIMAL(38,0))) AS huella FROM silver_voids
UNION ALL
SELECT 'gold_kpis_diarios' AS tabla, COUNT(*) AS filas, SUM(CAST(xxhash64(struct(*)) AS DECIMAL(38,0))) AS huella FROM gold_kpis_diarios
UNION ALL
SELECT 'gold_riesgo_empleados' AS tabla, COUNT(*) AS filas, SUM(CAST(xxhash64(struct(*)) AS DECIMAL(38,0))) AS huella FROM gold_riesgo_empleados
UNION ALL
SELECT 'gold_riesgo_tiendas' AS tabla, COUNT(*) AS filas, SUM(CAST(xxhash64(struct(*)) AS DECIMAL(38,0))) AS huella FROM gold_riesgo_tiendas;
