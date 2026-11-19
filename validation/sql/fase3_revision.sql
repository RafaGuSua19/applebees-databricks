-- Comparación de listas bajo el mismo presupuesto de revisión, sin etiquetas de auditoría.
-- Los 21 días finales se puntúan con datos estrictamente anteriores a cada fecha.
WITH corte AS (
  SELECT date_sub(max(dt), 20) AS inicio FROM gold_revision_descuentos
), muestra AS (
  SELECT s.*, (prioridad_dia <= 20 AND score >= 2) AS en_modelo
  FROM gold_revision_descuentos s CROSS JOIN corte
  WHERE s.dt >= corte.inicio
), presupuesto AS (
  SELECT dt, count_if(en_modelo) AS k FROM muestra GROUP BY dt
), evaluacion AS (
  SELECT m.*, m.prioridad_por_monto <= p.k AS en_base
  FROM muestra m JOIN presupuesto p USING (dt)
)
SELECT min(dt) AS desde, max(dt) AS hasta, count(*) AS candidatos,
       count_if(grupo_referencia = 'Tienda, canal y pago') AS con_referencia_local,
       count_if(grupo_referencia = 'Cadena, canal y pago') AS con_referencia_cadena,
       count_if(grupo_referencia = 'Historial insuficiente') AS sin_referencia,
       count_if(en_modelo) AS total_cola,
       count_if(en_base) AS total_base_monto,
       count_if(en_modelo AND en_base) AS en_ambas_listas,
       count_if(en_modelo AND NOT en_base) AS solo_modelo,
       count_if(en_modelo AND puntos_contexto > 0) AS cola_con_tasa_inusual,
       sum(CASE WHEN en_modelo THEN descuento ELSE 0 END) AS descuento_asociado_cola
FROM evaluacion
