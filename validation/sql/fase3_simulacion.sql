-- ¿Cuántos tickets y empleados sembrados encuentra la cola diaria (top 20 con al menos 2 puntos)?
-- Se compara con una lista ordenada solo por monto, con el mismo presupuesto de 20 por día.
-- Ejecutar en el esquema del target demo.
WITH t AS (
  SELECT s.dt, s.patron, s.EmployeeId,
         (r.prioridad_dia <= 20 AND r.score >= 2) AS en_cola,
         r.prioridad_por_monto <= 20 AS en_monto,
         r.score
  FROM sim_tickets_sembrados s
  LEFT JOIN gold_revision_descuentos r
    ON r.dt = s.dt AND r.LocationId = s.LocationId AND r.CheckId = s.CheckId
)
SELECT coalesce(patron, 'TOTAL') AS patron,
       count(*) AS tickets_sembrados,
       count_if(en_cola) AS tickets_en_cola,
       count_if(en_monto) AS tickets_por_monto,
       count(DISTINCT concat(dt, '|', EmployeeId)) AS empleado_dias,
       count(DISTINCT CASE WHEN en_cola THEN concat(dt, '|', EmployeeId) END) AS empleado_dias_en_cola,
       count(DISTINCT CASE WHEN en_monto THEN concat(dt, '|', EmployeeId) END) AS empleado_dias_por_monto,
       round(avg(score), 1) AS score_promedio,
       count_if(score IS NULL) AS sin_puntuar
FROM t
GROUP BY ROLLUP (patron)
ORDER BY patron NULLS LAST;
