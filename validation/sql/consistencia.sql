SELECT 'ticket_uniqueness' AS section,to_json(named_struct('silver_excess_rows',
 count(*)-count(DISTINCT struct(LocationId,dt,CheckId)))) AS metrics FROM silver_checks
UNION ALL
SELECT 'risk_population_grain',to_json(named_struct('employee_store_pairs',count(*),
 'distinct_employee_ids',count(DISTINCT EmployeeId),'zero_employee_ids',count_if(EmployeeId=0),
 'self_approved_evaluated_pairs',count_if(n_autoaprobados>0),
 'self_approved_positive_id_pairs',count_if(n_autoaprobados>0 AND EmployeeId>0)))
FROM gold_riesgo_empleados
UNION ALL
SELECT 'zero_employee_risk',to_json(named_struct('rows',count(*),'discount',sum(desc_emp),
 'self_approved_discount_rows',sum(n_autoaprobados),'score_min',min(score_riesgo),'score_max',max(score_riesgo)))
FROM gold_riesgo_empleados WHERE EmployeeId=0
UNION ALL
SELECT 'zero_employee_dimension',to_json(named_struct('rows',count(*)))
FROM silver_employees WHERE EmployeeId=0
UNION ALL
SELECT 'daily_worst_reconciliation',to_json(named_struct('days_below_95pct',count_if(rate<0.95),'minimum',min(rate)))
FROM (SELECT dt,avg(CASE WHEN abs(paid-(sold-disc_check+tax+tip))<=0.05 THEN 1.0 ELSE 0.0 END) AS rate
 FROM silver_checks GROUP BY dt)
UNION ALL
SELECT 'anomaly_overlap',to_json(named_struct('overdiscount_and_unreconciled',count_if(descuento>gross+0.05 AND abs(paid-(sold-disc_check+tax+tip))>0.05),
 'overdiscount_total',count_if(descuento>gross+0.05),'gross_sold_mismatch_max',max(abs(gross-sold-disc_item))))
FROM silver_checks;
