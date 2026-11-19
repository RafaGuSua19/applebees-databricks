-- ¿Cuántos tickets sembrados entran a la cola diaria (top 20 con al menos 2 puntos), por patrón?
-- Ejecutar en el esquema del target demo.
SELECT t.patron,
       count(*) AS sembrados,
       count_if(r.prioridad_dia <= 20 AND r.score >= 2) AS en_cola,
       round(100 * try_divide(count_if(r.prioridad_dia <= 20 AND r.score >= 2), count(*)), 1) AS pct_en_cola,
       count_if(r.prioridad_por_monto <= 20) AS en_top20_por_monto,
       round(avg(r.score), 2) AS score_promedio,
       count_if(r.CheckId IS NULL) AS sin_puntuar
FROM sim_tickets_sembrados t
LEFT JOIN gold_revision_descuentos r
  ON r.dt = t.dt AND r.LocationId = t.LocationId AND r.CheckId = t.CheckId
GROUP BY ROLLUP (t.patron)
ORDER BY t.patron NULLS LAST;
