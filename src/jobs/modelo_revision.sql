-- Una fila por ticket con descuento positivo y bruto positivo.
-- La referencia de tasas usa los 28 días previos. La señal de conducta usa el día cerrado.
-- v2: agrega la conducta del empleado que aplica descuentos discrecionales (MANAGER/WALKOUT)
-- frente a su propia historia, y limita la cola a 2 tickets por empleado y día.
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
), discrecional AS (
  -- Descuentos MANAGER/WALKOUT por empleado, tienda y día.
  SELECT dt, LocationId, EmployeeId, COUNT(*) AS n
  FROM {{schema}}.silver_discounts
  WHERE Amount > 0 AND DiscountName IN ('MANAGER', 'WALKOUT') AND EmployeeId > 0
  GROUP BY dt, LocationId, EmployeeId
), conducta AS (
  -- Últimos 7 días (incluye el día evaluado: la cola se publica al cierre) contra su promedio
  -- semanal de los 28 días anteriores a esa semana.
  SELECT dt, LocationId, EmployeeId,
         SUM(n) OVER w7 AS n_7d,
         coalesce(SUM(n) OVER w28, 0) / 4.0 AS base_semanal
  FROM discrecional
  WINDOW w7 AS (PARTITION BY LocationId, EmployeeId ORDER BY unix_date(dt) RANGE BETWEEN 6 PRECEDING AND CURRENT ROW),
         w28 AS (PARTITION BY LocationId, EmployeeId ORDER BY unix_date(dt) RANGE BETWEEN 34 PRECEDING AND 7 PRECEDING)
), conducta_puntos AS (
  SELECT *, CASE WHEN n_7d >= 12 AND n_7d >= 3 * base_semanal + 6 THEN 3
                 WHEN n_7d >= 8 AND n_7d >= 4 * base_semanal + 4 THEN 2 ELSE 0 END AS pts
  FROM conducta
), empleado_ticket AS (
  -- El ID menor deshace un empate y hace reproducible la atribución.
  SELECT x.dt, x.LocationId, x.CheckId,
         max_by(named_struct('emp', x.EmployeeId, 'n7', c.n_7d, 'base', c.base_semanal, 'pts', c.pts),
                struct(c.pts, c.n_7d, -x.EmployeeId)) AS e
  FROM (SELECT DISTINCT dt, LocationId, CheckId, EmployeeId FROM {{schema}}.silver_discounts
        WHERE Amount > 0 AND DiscountName IN ('MANAGER', 'WALKOUT') AND EmployeeId > 0) x
  JOIN conducta_puntos c ON c.dt = x.dt AND c.LocationId = x.LocationId AND c.EmployeeId = x.EmployeeId
  GROUP BY x.dt, x.LocationId, x.CheckId
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
         et.e.emp AS empleado_discrecional, et.e.n7 AS descuentos_7d, et.e.base AS base_semanal,
         coalesce(et.e.pts, 0) AS puntos_empleado,
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
  LEFT JOIN empleado_ticket et
    ON c.dt = et.dt AND c.LocationId = et.LocationId AND c.CheckId = et.CheckId
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
  SELECT *, puntos_contexto + puntos_autoaprobado + puntos_sin_gerente + puntos_duracion
            + puntos_empleado AS score
  FROM puntos
), diversidad AS (
  -- Orden del ticket entre los del mismo empleado discrecional ese día.
  SELECT *, row_number() OVER (PARTITION BY dt, empleado_discrecional,
                                CASE WHEN empleado_discrecional IS NULL THEN LocationId END,
                                CASE WHEN empleado_discrecional IS NULL THEN CheckId END
                               ORDER BY score DESC, descuento DESC, LocationId, CheckId) AS orden_empleado
  FROM scored
)
SELECT dt, LocationId, CheckId, CheckRevenueCenterId, tipo_pago, gross, descuento,
       con_advertencia, min_abierto, tasa_ticket, tasa_referencia, tickets_referencia,
       grupo_referencia, brecha_tasa, z_tasa, score, puntos_contexto, puntos_autoaprobado,
       puntos_sin_gerente, puntos_duracion, puntos_empleado, empleado_discrecional,
       descuentos_7d, round(base_semanal, 1) AS base_semanal, orden_empleado,
       concat_ws(' + ',
         IF(puntos_contexto > 0, 'Tasa inusual en su contexto', NULL),
         IF(autoaprobado, 'Autoaprobación registrada', NULL),
         IF(discrecional_sin_gerente, 'MANAGER/WALKOUT sin gerente identificado', NULL),
         IF(abierto_4h, 'Abierto al menos 4 h', NULL),
         IF(puntos_empleado > 0, concat('Empleado con ', descuentos_7d,
            ' MANAGER/WALKOUT en 7 días (antes ~', round(base_semanal, 1), ' por semana)'), NULL)) AS motivos,
       CASE WHEN orden_empleado <= 2 THEN
         row_number() OVER (PARTITION BY dt ORDER BY orden_empleado > 2, score DESC, descuento DESC,
                                                     LocationId, CheckId)
       END AS prioridad_dia,
       row_number() OVER (PARTITION BY dt ORDER BY descuento DESC, LocationId, CheckId)
         AS prioridad_por_monto,
       'contexto-28d-v2-empleado' AS version_modelo, current_timestamp() AS publicado_en
FROM diversidad
