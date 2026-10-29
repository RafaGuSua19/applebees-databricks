-- Contrato de publicación completo; también lo consume el job.
SELECT * FROM gold_calidad_datos;
-- Cobertura de cuarentena sin exponer JSON ni registros individuales.
SELECT _rescued_data AS motivo, COUNT(*) AS filas FROM bronze_checks GROUP BY ALL;
-- Población correcta: la unidad evaluada es empleado-tienda.
SELECT nivel_riesgo, COUNT(*) AS pares_empleado_tienda,
       COUNT(DISTINCT EmployeeId) AS ids_distintos, SUM(desc_emp) AS descuento_asociado
FROM gold_riesgo_empleados GROUP BY ALL ORDER BY nivel_riesgo;
