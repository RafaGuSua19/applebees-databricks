# Guion de Idea Submission

Duración propuesta de **4 minutos y 30 segundos**. La exposición en inglés sigue la presentación de Fase 2. Cada diapositiva del PowerPoint incluye notas del expositor.

## 0:00–0:30 · Business question

> Which discounted tickets should Applebee’s Operations review first each day, given limited review capacity? We’re proposing a daily queue that shows why each ticket stands out and gives the reviewer the evidence needed to follow up.

## 0:30–1:15 · What Phase 2 found

> Our baseline covers 2.14 million tickets from 127 stores. Cash accounted for 55.2% of discount dollars and 17.5% of gross sales. Tickets open at least four hours had a 21.2% discount rate, compared with 3.2% for shorter tickets. The To Go rate was also more than three times the In-Store rate. The earlier rules flagged 34 employee–store pairs. We’re using that evidence to ask which individual tickets deserve attention.

## 1:15–2:05 · What the model does

> The model compares each ticket’s discount rate with the previous 28 days for the same store, channel and payment type. When the store sample is small, it uses the chain’s matching channel and payment type. It also adds points for signals such as self-approval or a ticket left open for hours. For manager and walkout discounts, the model compares the employee’s last seven days with their own weekly average over the previous four weeks. That signal picks up sharp changes in behavior.

## 2:05–2:55 · Ingestion and data quality

> New daily files go into a Unity Catalog volume. Auto Loader tracks processed files. We keep tickets with a new field, a missing item ID or an unknown tip when the rest of the record is usable. Critical issues go into quarantine with the original record. Quality checks run before the queue is published. All twelve simulated days passed the quality gate. The five held-out runs took a median of four minutes and nineteen seconds from generation to publication.

## 2:55–3:45 · Dashboard demo and results

> We start on Discounts and filter by date, store, channel or payment. In Review Queue, we open one ticket and read its reasons and reference rate. On the last 21 real days, most tickets in the queue ranked outside the top 20 by amount. On the seven calibration days, the queue found 45 of 56 seeded employee-days, or 80 percent. That means at least one seeded ticket for that employee made the queue that day. Ranking by amount found 24, and the first version found 14.

Abrir **Descuentos → Cola de revisión → Simulación** en Databricks. En Cola de revisión elegir el **27 de agosto de 2026**, el último día de calibración. En Simulación quitar el filtro de fecha y elegir **Calibración** para mostrar los siete días del 21 al 27 de agosto. Si se agregaron más días de calibración, elegir también ese rango. Para mostrar el ensayo independiente, quitar el filtro de fecha y cambiar a **Prueba**.

## 3:45–4:30 · Final scope and success measure

> We then kept the rules fixed and tested five days with different employees, stores and patterns. Both versions found 8 of 37 seeded employee-days, or 22 percent. Ranking by amount found 4. Seven of the eight hits were card-paid walkouts. For the final, we’ll show the daily upload, the updated queue and the results for both cohorts. In a pilot, reviewers will record which cases were actionable, legitimate or needed more evidence. Our success measure is actionable cases per 20 reviews.

## Si preguntan

| Pregunta | Respuesta breve |
|---|---|
| ¿El score identifica fraude? | Prioriza una investigación humana. El resultado depende de política, evidencia y revisión del expediente. |
| ¿Por qué una ventana de 28 días? | Permite actualizar un patrón reciente y cubre cuatro semanas calendario. La ventana, mínimos y puntos se calibran con etiquetas operativas. |
| ¿Qué pasa si la tienda tiene pocos ejemplos? | Usa la cadena para el mismo canal y pago si alcanza el mínimo. Si tampoco alcanza, muestra la falta de referencia y sigue reportando los controles observados. |
| ¿Se entrena con información del futuro? | Cada tasa de referencia termina el día anterior al ticket. El score se puede recalcular con una llegada tardía de ese historial. |
| ¿Por qué se agregó la señal del empleado? | La simulación mostró que el abuso en efectivo no se veía: en efectivo lo normal ya es ~58 % de descuento, así que un 70 % no parece raro. El abuso es repetitivo, y eso sí se ve en la semana del empleado. |
| ¿No se llena la cola con un solo empleado? | No: entran máximo 2 tickets por empleado al día. El primer ticket lleva al revisor al resto. |
| ¿Los datos simulados son inventados? | Son tickets reales de un día equivalente con fechas recorridas. Solo los descuentos sembrados son inventados, y sabemos exactamente cuáles son. |
| ¿Qué significa el 80 %? | La cola detectó 45 de 56 empleado-días sembrados en calibración. Un día cuenta si al menos un ticket sembrado del empleado entró a la cola. El ensayo de prueba mide cobertura en otros patrones simulados. El piloto con revisores mide cuántos casos son accionables. |
| ¿Dónde quedan los llamados tickets malos? | En Bronze con JSON, archivo y motivo. Las advertencias recuperables siguen a Silver y aparecen en el dashboard. |
| ¿Por qué efectivo no suma puntos directamente? | El pago define el grupo de referencia. Cada ticket en efectivo se compara con su contexto de efectivo. |
| ¿Qué pasa si se reejecuta el job? | Auto Loader recuerda archivos. Si los insumos son los mismos, el ranking y los importes se conservan. La marca de publicación sí cambia. |
| ¿Qué significa el monto de la cola? | Es el descuento registrado en los tickets de esa selección. Un impacto económico requeriría una revisión adicional. |
| ¿Qué sigue después de esta entrega? | Piloto con revisores, monitoreo de frescura y validación de señales para los patrones con baja cobertura. |

[Documentación técnica y alcance de la entrega](fase3.md)
