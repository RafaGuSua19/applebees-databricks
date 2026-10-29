SELECT 'self_approval_in_evaluated_population' AS section,to_json(named_struct(
 'employee_store_pairs',count_if(n_autoaprobados>0),
 'distinct_employee_ids',count(DISTINCT CASE WHEN n_autoaprobados>0 THEN EmployeeId END),
 'risk_rows_zero_id',count_if(EmployeeId=0),
 'autoapproved_rows_zero_id',sum(CASE WHEN EmployeeId=0 THEN n_autoaprobados ELSE 0 END),
 'unmatched_employee_dimension',count_if(e.EmployeeId IS NULL))) AS metrics
FROM gold_riesgo_empleados g LEFT JOIN silver_employees e USING(EmployeeId)
UNION ALL
SELECT 'self_approval_discount_population',to_json(named_struct(
 'zero_id_discount_rows',count_if(autoaprobado AND EmployeeId=0 AND Amount>0),
 'positive_id_discount_rows',count_if(autoaprobado AND EmployeeId>0 AND Amount>0),
 'positive_employee_ids',count(DISTINCT CASE WHEN autoaprobado AND EmployeeId>0 AND Amount>0 THEN EmployeeId END),
 'zero_id_discount_amount',sum(CASE WHEN autoaprobado AND EmployeeId=0 AND Amount>0 THEN Amount ELSE 0 END),
 'zero_id_discount_count',count_if(EmployeeId=0 AND Amount>0)))
FROM silver_discounts
UNION ALL
SELECT 'risk_high_signals',to_json(named_struct('high',count(*),'cash_ge_half',count_if(pct_efectivo>=0.5),
 'at_least_five_long_tickets',count_if(tickets_4h_con_desc>=5),'manager_walkout_ge_30pct',count_if(pct_manager_walkout>=0.3),
 'missing_manager_ge_10pct',count_if(pct_sin_gerente>=0.1),'discount_ge_2x',count_if(veces_vs_tienda>=2)))
FROM gold_riesgo_empleados WHERE nivel_riesgo='Alto'
UNION ALL
SELECT 'risk_cash_signal',to_json(named_struct('total',count(*),'cash_rule_count',count_if(pct_efectivo>=0.5)))
FROM gold_riesgo_empleados
UNION ALL
SELECT concat('negative_payment_',PayCatName),to_json(named_struct('rows',count(*),'amount',sum(Amount)))
FROM silver_payments WHERE Amount<0 GROUP BY PayCatName
UNION ALL
SELECT 'cash_comparison_excluding_employee_meals',to_json(named_struct('type',c.tipo_pago,'tickets',count(*),
 'gross',sum(c.gross),'discount',sum(c.descuento),'rate',try_divide(sum(c.descuento),sum(c.gross))))
FROM silver_checks c LEFT ANTI JOIN (
 SELECT DISTINCT LocationId,dt,CheckId FROM silver_discounts WHERE categoria='Empleado'
) d USING(LocationId,dt,CheckId)
WHERE c.tipo_pago IN ('Efectivo','Tarjeta crédito') GROUP BY c.tipo_pago
UNION ALL
SELECT 'tip_clipping_impact',to_json(named_struct('preserved_total_tip',sum(tip),
 'hypothetical_clipped_total_tip',sum(greatest(tip,0)),'clipped_amount',sum(greatest(tip,0)-tip)))
FROM silver_checks;
