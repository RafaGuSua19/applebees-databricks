# Demo: insertar un día nuevo y verlo llegar a la cola de revisión

## Qué vamos a demostrar

El dataset termina el 20 de agosto. Para mostrar el pipeline como funcionaría en operación diaria, **generamos días nuevos** (21 ago, 22 ago…) y los dejamos caer en un volumen. El job de simulación dispara la orquestación diaria: Auto Loader detecta el archivo, la compuerta revisa calidad, el modelo puntúa los tickets y el dashboard muestra la cola del día nuevo.

Además, en cada día simulado **sembramos tickets con abuso conocido**. Como sabemos cuáles son, podemos medir algo que con el histórico no se puede: **¿cuántos de esos tickets entran a la cola de 20?**

## Cómo funciona por dentro

```
Simulador ──► Volumen demo ──► Auto Loader ──► Silver ──► Compuerta ──► Modelo por ticket ──► Dashboard
(día nuevo)   (1 archivo/día)   (solo lo nuevo)  (limpio)   (calidad)     (cola de 20)          (4 páginas)
```

1. **Simulador** (`src/simulacion/simulador_tickets.py`). Toma un día real con el mismo día de la semana (un viernes simulado parte de un viernes real), conserva entre 85 % y 100 % de los tickets de cada tienda y recorre las fechas al día nuevo. El archivo tiene exactamente el formato de la fuente.
2. **Abuso sembrado.** Se eligen 8 empleados (uno por tienda) y, en el día simulado, unos 15 de sus tickets reciben un descuento con uno de 4 patrones:

   | Patrón | Qué hace | Qué esperamos del modelo |
   |---|---|---|
   | `efectivo_manager` | MANAGER de 50–90 %, cobrado en efectivo | Probablemente **0 puntos** (ver nota) |
   | `walkout_sin_gerente` | WALKOUT de 60–90 % sin gerente, en efectivo | 1 punto (sin gerente): no alcanza el mínimo de 2 |
   | `autoaprobado_4h` | Se autoriza a sí mismo y el ticket queda abierto 4 h o más | 3 puntos (2 + 1): compite por la cola |
   | `sutil` | MANAGER de 15–30 %, cobrado con tarjeta | Pocos o ningún punto (prueba de sensibilidad) |

   **Hipótesis del equipo.** En la muestra analizada de efectivo en salón, una referencia de 58 % y una desviación de 39 puntos porcentuales colocarían el umbral de dos desviaciones por encima de 100 %. El comportamiento depende del grupo de referencia. El ensayo mide sensibilidad con las reglas actuales.

   Cada ticket alterado se vuelve a cuadrar (impuesto y pago), así que la compuerta de calidad no se rompe. Los tickets sembrados quedan en `sim_tickets_sembrados` y cada día generado en `sim_bitacora`.
3. **El archivo se escribe primero en `_staging/`.** El simulador guarda las etiquetas por fecha y mueve el archivo completo a `facts/checks/brand=rmh_sim/dt=AAAA-MM-DD/`. Si se interrumpe antes del movimiento, un reintento puede reconstruir las etiquetas del mismo día.
4. **El job `applebees_simulacion`** genera el día y luego dispara la orquestación diaria normal: pipeline → compuerta → publicación de la cola.

## Preparación (una sola vez, el día anterior)

1. Usar la rama `fase3-idea-submission`. El bundle define dos dashboards. El de `phase3` conserva las tres vistas del histórico y el de `demo` agrega Simulación y el filtro Real / Simulado.
2. Desplegar el target de demo:
   ```bash
   databricks bundle deploy -t demo --var dashboard_warehouse_id=ID_DEL_WAREHOUSE
   ```
3. Preparar el volumen de demo: en Databricks abrir el notebook `src/simulacion/simulador_tickets` (dentro de la carpeta del bundle), poner `accion = preparar`, `schema = applebees_demo`, `destino = /Volumes/workspace/default/applebees_demo` y correrlo. Copia los catálogos y los últimos 35 días reales (unos 4 GB). El modelo usa 28 días de contexto, así que el primer día simulado ya tiene historia completa.
4. Primera carga del pipeline de demo:
   ```bash
   databricks bundle run daily_orchestration_job -t demo --var dashboard_warehouse_id=ID_DEL_WAREHOUSE
   ```
5. **Ensayo:** correr el job de simulación 2 o 3 veces para tener días simulados y números de detección:
   ```bash
   databricks bundle run simulacion_job -t demo --var dashboard_warehouse_id=ID_DEL_WAREHOUSE
   ```
   **Medir cuánto tarda cada corrida.** Con ese tiempo decidimos si la corrida en vivo cabe en el pitch.
6. Abrir el dashboard de demo, ir a **Simulación** y revisar `validation/sql/fase3_simulacion.sql`. Anotar el % de sembrados que entra a la cola por patrón: ese es el resultado que vamos a contar.

## Ensayos completados en Databricks

[Dashboard de demo](https://dbc-eb170ead-6845.cloud.databricks.com/dashboardsv3/01f1e3d2467715c89940a6cd05daec17/published?w=7474659154935244) · [Dashboard de datos reales](https://dbc-eb170ead-6845.cloud.databricks.com/dashboardsv3/01f1e3bc8da91e4d95ee22717db572ee/published?w=7474659154935244)

Se copiaron 35 días reales, del 17 de julio al 20 de agosto de 2026. La [preparación](https://dbc-eb170ead-6845.cloud.databricks.com/?o=7474659154935244#job/871414720392241/run/191789031304602) tardó 144.8 s y la [carga base](https://dbc-eb170ead-6845.cloud.databricks.com/jobs/737955808701802/runs/426669643952349?o=7474659154935244) tardó 184.1 s. Los tiempos de los ensayos incluyen generación, ingesta incremental, calidad y publicación de la cola.

| Día de negocio y corrida | Tiempo | Tickets generados | Sembrados | En la cola | En el top 20 por importe |
|---|---:|---:|---:|---:|---:|
| [21 de agosto](https://dbc-eb170ead-6845.cloud.databricks.com/jobs/313690563199164/runs/515253697281654?o=7474659154935244) | 270.4 s | 22,346 | 112 | 10 | 4 |
| [22 de agosto](https://dbc-eb170ead-6845.cloud.databricks.com/jobs/313690563199164/runs/922274298740216?o=7474659154935244) | 261.5 s | 18,650 | 92 | 13 | 9 |
| Total | | 40,996 | 204 | 23 | 13 |

Resultado de [fase3_simulacion.sql](../validation/sql/fase3_simulacion.sql) sobre ambos ensayos.

| Patrón | Sembrados | En cola | % en cola | Top 20 por importe | Puntaje promedio |
|---|---:|---:|---:|---:|---:|
| `autoaprobado_4h` | 59 | 23 | 39.0% | 3 | 3.0 |
| `efectivo_manager` | 54 | 0 | 0.0% | 6 | 0.0 |
| `sutil` | 24 | 0 | 0.0% | 0 | 0.0 |
| `walkout_sin_gerente` | 67 | 0 | 0.0% | 4 | 1.0 |
| Total | 204 | 23 | 11.3% | 13 | 1.2 |

El modelo puntuó los 204 casos. Las 23 entradas en la cola fueron autoaprobaciones de tickets abiertos al menos cuatro horas. La comparación por importe seleccionó 13 casos sembrados y cubrió otros patrones. Estos resultados corresponden a casos sembrados en el ensayo.

La demo quedó en 37 archivos y 668,743 tickets admitidos, con cero duplicados y cero registros en cuarentena. `phase3` permaneció en 115 archivos, 2,142,846 tickets y fecha de corte del 20 de agosto. Pasaron las 15 pruebas locales y las 29 consultas de widgets de `phase3` y 43 de `demo`. La página Simulación vive en el dashboard de demo y usa las etiquetas de `sim_tickets_sembrados`, la bitácora y el score existente.

Para el pitch, mostrar el día del **22 de agosto ya procesado**. Las dos corridas completas tardaron más de cuatro minutos.

## La demo en vivo

1. Si quieren mostrar el job en marcha, lanzar `applebees_simulacion` antes del pitch desde *Jobs & Pipelines → Run now* y dejar el día del 22 de agosto seleccionado para la parte de resultados.
2. **Mostrar el job corriendo** (vista de tareas): *"Acaba de llegar el archivo del siguiente día. Auto Loader procesa el archivo nuevo y la compuerta revisa calidad antes de publicar la cola."*
3. **Dashboard → Descuentos:** filtrar *Datos = Simulado*. *"Los días simulados tienen un volumen y una tasa parecidos a los reales; la tasa sube un poco por los descuentos sembrados."* (Confirmarlo con los números del ensayo.)
4. **Dashboard → Cola de revisión:** elegir el último día. Abrir un ticket con motivos *"Autoaprobación registrada + Abierto al menos 4 h"*. *"Este es uno de los tickets que sembramos. El modelo lo puso en la cola y explica por qué."* Señalar el contador **Fuera del top 20 por monto**: *"Estos casos no los vería alguien que solo ordena por monto."*
5. **Dashboard → Simulación:** *"De N tickets sembrados, X % entró a la cola. El patrón sutil casi no entra, y es lo esperado: un descuento de 20 % con tarjeta no se distingue de una promoción."*

Si la corrida en vivo no termina a tiempo, se muestra el día simulado anterior; ya está procesado desde el ensayo.

## Si preguntan

| Pregunta | Respuesta |
|---|---|
| ¿Los datos simulados son inventados? | Son tickets reales de un día equivalente, con fechas recorridas. Lo único inventado son los descuentos sembrados, y sabemos exactamente cuáles son. |
| ¿Por qué no dejar el pipeline en modo continuo? | Los datos llegan una vez al día. En modo *triggered* solo pagamos cómputo cuando llega un archivo. |
| ¿Afecta a los datos oficiales? | No. La demo tiene su propio volumen y esquema (`applebees_demo`). La fuente original solo se lee. |
| ¿Qué pasa si el archivo viene mal? | Se queda en cuarentena en Bronze con su motivo, y la compuerta no publica la cola. |
| ¿Se puede repetir? | Sí. Con la misma semilla, el simulador genera los mismos tickets. |

## Repetir el ensayo

Cada nueva corrida genera el siguiente día de negocio y conserva las corridas anteriores. Las dos programaciones del target `demo` se mantienen pausadas durante el ensayo.
