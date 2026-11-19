-- Una fila por ticket con descuento positivo y bruto positivo.
-- Para cada fecha, el modelo aprende exclusivamente de los 28 días anteriores.
WITH candidatos AS (
  SELECT dt, LocationId, CheckId, CheckRevenueCenterId, tipo_pago, gross, descuento,
         size(_dq_warnings) > 0 AS con_advertencia, min_abierto,
         CAST(descuento AS DOUBLE) / CAST(gross AS DOUBLE) AS tasa_ticket
  FROM {{schema}}.silver_checks
  WHERE gross > 0 AND descuento > 0
), autorizaciones AS (
  SELECT dt, LocationId, CheckId,
         COUNT_IF(autoaprobado) > 0 AS autoaprobado,
         COUNT_IF(sin_gerente AND DiscountName IN ('MANAGER', 'WALKOUT')) > 0 AS discrecional_sin_gerente
  FROM {{schema}}.silver_discounts
  WHERE Amount > 0
  GROUP BY dt, LocationId, CheckId
), dias AS (
  SELECT dt, LocationId, CheckRevenueCenterId, tipo_pago,
         COUNT(*) AS n, SUM(least(tasa_ticket, 1.0)) AS suma,
         SUM(power(least(tasa_ticket, 1.0), 2)) AS suma_cuadrados
  FROM candidatos
  GROUP BY GROUPING SETS (
    (dt, LocationId, CheckRevenueCenterId, tipo_pago),
    (dt, CheckRevenueCenterId, tipo_pago)
  )
), historia AS (
  SELECT dt, LocationId, CheckRevenueCenterId, tipo_pago,
         SUM(n) OVER w AS n, COUNT(*) OVER w AS dias_activos,
         SUM(suma) OVER w AS suma, SUM(suma_cuadrados) OVER w AS suma_cuadrados
  FROM dias
  WINDOW w AS (
    PARTITION BY LocationId, CheckRevenueCenterId, tipo_pago
    ORDER BY unix_date(dt) RANGE BETWEEN 28 PRECEDING AND 1 PRECEDING
  )
), contexto AS (
  SELECT c.*, coalesce(a.autoaprobado, false) AS autoaprobado,
         coalesce(a.discrecional_sin_gerente, false) AS discrecional_sin_gerente,
         coalesce(c.min_abierto >= 240, false) AS abierto_4h,
         CASE WHEN l.n >= 50 AND l.dias_activos >= 7 THEN 'Tienda, canal y pago'
              WHEN r.n >= 200 AND r.dias_activos >= 7 THEN 'Cadena, canal y pago'
              ELSE 'Historial insuficiente' END AS grupo_referencia,
         CASE WHEN l.n >= 50 AND l.dias_activos >= 7 THEN l.n
              WHEN r.n >= 200 AND r.dias_activos >= 7 THEN r.n END AS tickets_referencia,
         CASE WHEN l.n >= 50 AND l.dias_activos >= 7 THEN l.suma / l.n
              WHEN r.n >= 200 AND r.dias_activos >= 7 THEN r.suma / r.n END AS tasa_referencia,
         CASE WHEN l.n >= 50 AND l.dias_activos >= 7 THEN l.suma_cuadrados / l.n
              WHEN r.n >= 200 AND r.dias_activos >= 7 THEN r.suma_cuadrados / r.n END AS segundo_momento
  FROM candidatos c
  LEFT JOIN historia l
    ON c.dt = l.dt AND c.LocationId = l.LocationId
   AND c.CheckRevenueCenterId IS NOT DISTINCT FROM l.CheckRevenueCenterId AND c.tipo_pago = l.tipo_pago
  LEFT JOIN historia r
    ON c.dt = r.dt AND r.LocationId IS NULL
   AND c.CheckRevenueCenterId IS NOT DISTINCT FROM r.CheckRevenueCenterId AND c.tipo_pago = r.tipo_pago
  LEFT JOIN autorizaciones a
    ON c.dt = a.dt AND c.LocationId = a.LocationId AND c.CheckId = a.CheckId
), desviaciones AS (
  SELECT *, tasa_ticket - tasa_referencia AS brecha_tasa,
         CASE WHEN tasa_referencia IS NOT NULL THEN (tasa_ticket - tasa_referencia)
           / greatest(0.02, sqrt(greatest(0.0, segundo_momento - power(tasa_referencia, 2)))) END AS z_tasa
  FROM contexto
), puntos AS (
  SELECT *,
         CASE WHEN z_tasa >= 3 AND brecha_tasa >= 0.10 THEN 3
              WHEN z_tasa >= 2 AND brecha_tasa >= 0.08 THEN 2 ELSE 0 END AS puntos_contexto,
         CASE WHEN autoaprobado THEN 2 ELSE 0 END AS puntos_autoaprobado,
         CASE WHEN discrecional_sin_gerente THEN 1 ELSE 0 END AS puntos_sin_gerente,
         CASE WHEN abierto_4h THEN 1 ELSE 0 END AS puntos_duracion
  FROM desviaciones
), scored AS (
  SELECT *, puntos_contexto + puntos_autoaprobado + puntos_sin_gerente + puntos_duracion AS score
  FROM puntos
)
SELECT dt, LocationId, CheckId, CheckRevenueCenterId, tipo_pago, gross, descuento,
       con_advertencia, min_abierto, tasa_ticket, tasa_referencia, tickets_referencia,
       grupo_referencia, brecha_tasa, z_tasa, score, puntos_contexto, puntos_autoaprobado,
       puntos_sin_gerente, puntos_duracion,
       concat_ws(' + ',
         IF(puntos_contexto > 0, 'Tasa inusual en su contexto', NULL),
         IF(autoaprobado, 'Autoaprobación registrada', NULL),
         IF(discrecional_sin_gerente, 'MANAGER/WALKOUT sin gerente identificado', NULL),
         IF(abierto_4h, 'Abierto al menos 4 h', NULL)) AS motivos,
       row_number() OVER (PARTITION BY dt ORDER BY score DESC, descuento DESC, LocationId, CheckId)
         AS prioridad_dia,
       row_number() OVER (PARTITION BY dt ORDER BY descuento DESC, LocationId, CheckId)
         AS prioridad_por_monto,
       'contexto-28d-v1' AS version_modelo, current_timestamp() AS publicado_en
FROM scored
