SELECT 'quality_gate' AS section, to_json(struct(*)) AS metrics FROM gold_calidad_datos
UNION ALL
SELECT 'ticket_totals', to_json(named_struct(
 'tickets',count(*),'days',count(DISTINCT dt),'stores',count(DISTINCT LocationId),
 'first_date',min(dt),'last_date',max(dt),'gross',sum(gross),'discount',sum(descuento),
 'discount_rate',try_divide(sum(descuento),sum(gross)),
 'discount_on_fully_discounted',sum(CASE WHEN cien_pct_desc THEN descuento ELSE 0 END),
 'fully_discounted_tickets',count_if(cien_pct_desc),
 'not_reconciled',count_if(abs(paid-(sold-disc_check+tax+tip))>0.05))) FROM silver_checks
UNION ALL
SELECT concat('risk_',nivel_riesgo), to_json(named_struct('employees_store_pairs',count(*),'stores',count(DISTINCT LocationId),
 'discount_ge_3x_store',count_if(veces_vs_tienda>=3),'zero_store_median_with_discount',count_if(mediana_tienda=0 AND desc_emp>0),
 'unknown_employee',count_if(EmployeeId IS NULL OR EmployeeId=0)))
FROM gold_riesgo_empleados GROUP BY nivel_riesgo
UNION ALL
SELECT concat('payment_',tipo_pago),to_json(named_struct('tickets',sum(tickets),'gross',sum(venta_bruta),'discount',sum(descuento),
 'rate',try_divide(sum(descuento),sum(venta_bruta)))) FROM gold_kpis_diarios GROUP BY tipo_pago
UNION ALL
SELECT concat('channel_',coalesce(Canal,'NULL')),to_json(named_struct('tickets',sum(tickets),'gross',sum(venta_bruta),
 'discount',sum(descuento),'rate',try_divide(sum(descuento),sum(venta_bruta)))) FROM gold_kpis_diarios GROUP BY Canal
UNION ALL
SELECT concat('duration_',cast(abierto_4h AS STRING)),to_json(named_struct('tickets',count(*),'gross',sum(gross),
 'discount',sum(descuento),'rate',try_divide(sum(descuento),sum(gross)))) FROM silver_checks GROUP BY abierto_4h
UNION ALL
SELECT concat('category_',categoria),to_json(named_struct('discount_rows',count(*),'amount',sum(Amount)))
FROM silver_discounts GROUP BY categoria
UNION ALL
SELECT 'self_approval',to_json(named_struct('employee_ids',count(DISTINCT EmployeeId),
 'employee_store_pairs',count(DISTINCT struct(LocationId,EmployeeId)),'discount_rows',count(*),'amount',sum(Amount)))
FROM silver_discounts WHERE autoaprobado AND Amount>0
UNION ALL
SELECT 'gold_consistency',to_json(named_struct('gold_tickets',sum(tickets),'gold_gross',sum(venta_bruta),'gold_discount',sum(descuento)))
FROM gold_kpis_diarios;
