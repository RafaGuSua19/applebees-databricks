# Guion de Idea Submission

Duración propuesta de **4 minutos y 30 segundos**. La exposición en inglés sigue la presentación de Fase 2. Cada diapositiva del PowerPoint incluye notas del expositor.

## 0:00–0:30 · Business question

> Which discounted tickets should Applebee’s Operations review first each day, given limited review capacity? We’re proposing a daily queue that shows why each ticket stands out and gives the reviewer the evidence needed to follow up.

## 0:30–1:15 · What Phase 2 found

> Our baseline covers 2.14 million tickets from 127 stores. Cash accounted for 55.2% of discount dollars and 17.5% of gross sales. Tickets open at least four hours had a 21.2% discount rate, compared with 3.2% for shorter tickets. The To Go rate was also more than three times the In-Store rate. The earlier rules flagged 34 employee–store pairs. We’re using that evidence to ask which individual tickets deserve attention.

## 1:15–2:05 · What the model does

> For each ticket, the model looks back 28 days and compares its discount rate with checks from the same store, channel and payment type. It uses the chain’s matching channel and payment type when the local sample is too small. Then it adds points for visible authorization or closure signals. In this example, the ticket is third by dollar amount and first in the queue. Its rate is 40% versus a 10% reference, it has a recorded self-approval and it stayed open more than four hours.

## 2:05–2:55 · Ingestion and data quality

> New daily files go into a Unity Catalog volume. Auto Loader tracks files that already ran. We keep tickets that have a new field, a missing item ID or an unknown tip when the rest of the record is usable. For example, a missing tip stays unknown while the sale and discount contribute to their metrics. A record with a critical issue goes into quarantine with its original evidence. Quality checks run before we publish the next queue. In our two-file replay, Bronze moved from one row to three, and a third run kept three. The ticket with warnings stayed usable.

## 2:55–3:45 · Dashboard demo

> We can start on Discounts and filter by business date, store, channel or payment. Then we move to Review Queue and read one ticket’s reasons and reference rate. Across the last 21 historical days, 371 of 420 picks differed from the amount-only ranking, under the same daily capacity. Quality and Freshness shows which business day reached the pipeline, when scoring was published and how many records were retained with warnings or quarantined.

Abrir el dashboard de Databricks. En vivo, abrir **Descuentos → Cola de revisión → Calidad y frescura**. Filtrar al **20 de agosto de 2026** en Cola de revisión. Hay 20 tickets con motivos y referencia contextual. La fecha del negocio y la hora de procesamiento cuentan cosas diferentes. El caso de 40% frente a 10% es la alternativa ilustrativa si el warehouse tarda en cargar.

## 3:45–4:30 · Final scope and success measure

> At the final presentation, we will show the ingestion replay, the quality evidence, the ticket model and the dashboard. We’ll also compare our queue with a simple ranking by discount amount, under the same review capacity. In a pilot, reviewers will record which cases were actionable, legitimate or had insufficient evidence. Our success measure is actionable cases per 20 reviews.

## Si preguntan

| Pregunta | Respuesta breve |
|---|---|
| ¿El score identifica fraude? | Prioriza una investigación humana. El resultado depende de política, evidencia y revisión del expediente. |
| ¿Por qué una ventana de 28 días? | Permite actualizar un patrón reciente y cubre cuatro semanas calendario. La ventana, mínimos y puntos se calibran con etiquetas operativas. |
| ¿Qué pasa si la tienda tiene pocos ejemplos? | Usa la cadena para el mismo canal y pago si alcanza el mínimo. Si tampoco alcanza, muestra la falta de referencia y sigue reportando los controles observados. |
| ¿Se entrena con información del futuro? | Cada tasa de referencia termina el día anterior al ticket. El score se puede recalcular con una llegada tardía de ese historial. |
| ¿Dónde quedan los llamados tickets malos? | En Bronze con JSON, archivo y motivo. Las advertencias recuperables siguen a Silver y aparecen en el dashboard. |
| ¿Por qué efectivo no suma puntos directamente? | El pago define el grupo de referencia. Cada ticket en efectivo se compara con su contexto de efectivo. |
| ¿Qué pasa si se reejecuta el job? | Auto Loader recuerda archivos. Si los insumos son los mismos, el ranking y los importes se conservan. La marca de publicación sí cambia. |
| ¿Qué significa el monto de la cola? | Es el descuento registrado en los tickets de esa selección. Un impacto económico requeriría una revisión adicional. |
| ¿Qué sigue después de esta entrega? | Piloto humano con presupuesto fijo, prueba de una llegada nueva, monitoreo de frescura y ajuste de umbrales. |

[Documentación técnica y alcance de la entrega](fase3.md)
