CREATE MATERIALIZED VIEW gold_incidencias_ingesta
COMMENT 'Resumen de incidencias por archivo y motivo, sin JSON original ni identificadores de personas'
AS SELECT
  dt,
  regexp_extract(_source_file, '([^/]+)$', 1) AS archivo,
  CASE WHEN _rescued_data IS NOT NULL THEN 'Cuarentena' ELSE 'Advertencia' END AS estado,
  coalesce(_rescued_data, concat_ws(' + ', _dq_warnings)) AS motivo,
  COUNT(*) AS registros
FROM bronze_checks
WHERE _rescued_data IS NOT NULL OR size(_dq_warnings) > 0
GROUP BY ALL;
