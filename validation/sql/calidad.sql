SELECT 'bronze' AS section,to_json(named_struct('rows',count(*),'files',count(DISTINCT _source_file),
 'rescued',count_if(_rescued_data IS NOT NULL),'incomplete_key',count_if(LocationId IS NULL OR dt IS NULL OR Id IS NULL),
 'date_mismatch',count_if(try_cast(substr(BusinessDate,1,10) AS DATE)<>dt),'missing_business_date',count_if(BusinessDate IS NULL),
 'source_items',sum(coalesce(array_size(ItemsSold),0)),'source_payments',sum(coalesce(array_size(Payments),0)),
 'gross_missing',sum(size(filter(ItemsSold,x->x.GrossPrice IS NULL))),
 'itemid_missing',sum(size(filter(ItemsSold,x->x.ItemId IS NULL))))) AS metrics FROM bronze_checks
UNION ALL
SELECT 'silver_checks',to_json(named_struct('rows',count(*),'invalid_time',count_if(min_abierto IS NULL OR min_abierto<0),
 'negative_gross',count_if(gross<0),'discount_over_gross',count_if(descuento>gross+0.05),
 'gross_sold_discount_mismatch',count_if(abs(gross-sold-disc_item)>0.05),'negative_tips',count_if(tip<0),
 'nonzero_servicecharge',count_if(ServiceCharge<>0),'no_items',count_if(n_items=0))) FROM silver_checks
UNION ALL
SELECT 'silver_items',to_json(named_struct('rows',count(*),'incomplete_ticket_key',count_if(LocationId IS NULL OR dt IS NULL OR CheckId IS NULL),
 'negative_gross',count_if(GrossPrice<0),'missing_employee',count_if(EmployeeId IS NULL),'missing_item_id',count_if(ItemId IS NULL)))
FROM silver_items
UNION ALL
SELECT 'silver_discounts',to_json(named_struct('rows',count(*),'incomplete_ticket_key',count_if(LocationId IS NULL OR dt IS NULL OR CheckId IS NULL),
 'negative_amount',count_if(Amount<0),'missing_amount',count_if(Amount IS NULL),'missing_employee',count_if(EmployeeId IS NULL),
 'empty_name',count_if(DiscountName IS NULL OR trim(DiscountName)='')))
FROM silver_discounts
UNION ALL
SELECT 'silver_payments',to_json(named_struct('rows',count(*),'negative_amount',count_if(Amount<0),
 'negative_tip',count_if(Tip<0),'missing_amount',count_if(Amount IS NULL),
 'payment_names_trimmed',count_if(PayCatName<>trim(PayCatName)))) FROM silver_payments
UNION ALL
SELECT 'dimension_coverage',to_json(named_struct('unmatched_store',count_if(l.LocationId IS NULL),
 'unmatched_channel',count_if(r.CheckRevenueCenterId IS NULL)))
FROM silver_checks c LEFT JOIN silver_locations l USING(LocationId)
LEFT JOIN silver_revenue_centers r USING(CheckRevenueCenterId)
UNION ALL
SELECT 'employee_coverage',to_json(named_struct('risk_rows',count(*),'missing_hire_date',count_if(HireDate IS NULL),
 'negative_tenure',count_if(anios_antiguedad<0),'null_risk_ratio',count_if(veces_vs_tienda IS NULL),
 'null_employee',count_if(EmployeeId IS NULL))) FROM gold_riesgo_empleados;
