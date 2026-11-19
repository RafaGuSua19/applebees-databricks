-- Ejecutar antes y después de un refresh incremental sin archivos nuevos.
-- Se omite la hora de publicación, que refleja cada ejecución.
SELECT 'bronze_checks' AS tabla, count(*) AS filas,
       sum(CAST(xxhash64(_source_file, _record_index, _raw_record, _rescued_data, _dq_warnings)
         AS DECIMAL(38,0))) AS huella
FROM bronze_checks
UNION ALL
SELECT 'gold_kpis_diarios', count(*),
       sum(CAST(xxhash64(struct(*)) AS DECIMAL(38,0)))
FROM gold_kpis_diarios
UNION ALL
SELECT 'gold_revision_descuentos', count(*),
       sum(CAST(xxhash64(dt, LocationId, CheckId, CheckRevenueCenterId, tipo_pago, gross, descuento,
         con_advertencia, min_abierto, round(tasa_ticket, 9), round(tasa_referencia, 9), tickets_referencia,
         grupo_referencia, round(brecha_tasa, 9), round(z_tasa, 9), score, puntos_contexto,
         puntos_autoaprobado, puntos_sin_gerente, puntos_duracion, motivos, prioridad_dia,
         prioridad_por_monto, version_modelo) AS DECIMAL(38,0)))
FROM gold_revision_descuentos
ORDER BY tabla
