SELECT count(*) AS total_kpi_rows,
 count_if(pct_desc<0 OR pct_desc>1) AS strict_failures,
 count_if(NOT (pct_desc <=> CAST(try_divide(CAST(descuento AS DECIMAL(24,2)),
   CAST(venta_bruta AS DECIMAL(24,2))) AS DECIMAL(18,9)))) AS inconsistent_rates,
 count_if(pct_desc<0) AS negative_rates,
 count_if(pct_desc>1) AS rates_over_one,
 count_if(pct_desc < -0.000000001 OR pct_desc > 1.000000001) AS failures_beyond_float_tolerance,
 min(pct_desc) AS minimum_rate,max(pct_desc) AS maximum_rate,
 count_if(pct_desc>1 AND pct_desc<=1.000000001) AS near_one_rounding,
 count_if(pct_desc<0 AND pct_desc>=-0.000000001) AS near_zero_rounding
FROM gold_kpis_diarios;
