# Archivos de la entrega y push a main

La entrega está integrada en la raíz del repositorio; no hay una segunda copia de código que deba elegirse manualmente. Las correcciones se guardaron en `f719b2a` y se integró el diccionario remoto de `ca25dd5`, conservando ambas historias. La integración solo modifica documentación y no publica cambios en GitHub.

## Archivos incluidos

La entrega versiona estas rutas:

- `.gitignore`, `README.md`, `databricks.yml`.
- `.github/workflows/`: comprobación de sintaxis y reglas locales en push/PR.
- `resources/`: pipeline, orquestación y job de QA.
- `src/`: transformaciones y tareas corregidas.
- `exploration/`: notebooks de solo lectura, ejecutados en QA.
- `tests/`: pruebas locales y aceptación en Databricks.
- `scripts/`: validación, evidencia y generación reproducible de figura.
- `validation/`: consultas agregadas y manifiesto de fuentes validadas.
- `docs/`: cobertura de rúbrica, calidad, diccionario, operación, evidencia y figura de negocio.

## No incluir

`.local/` y `.databricks/` están ignorados. En `.local/auditoria_original/` se conservaron los documentos y consultas de la revisión anterior; en `.local/validation/` están los resultados brutos de esta revisión. Las credenciales se mantienen fuera del repositorio. Los datos de la empresa continúan en Unity Catalog.

## Revisar y publicar

Los cambios ya están guardados en commits. Desde la raíz, verificar el estado y la divergencia antes de publicar:

```bash
python3 scripts/validate_local.py
shasum -a 256 -c validation/source_manifest.sha256
git status --short
git log -4 --oneline --graph
git fetch origin
git rev-list --left-right --count HEAD...origin/main
```

`git status --short` debe estar vacío. En el último comando, el primer número cuenta los commits locales pendientes de publicar y el segundo los commits remotos pendientes de integrar. Si el segundo es cero, se puede publicar con:

```bash
git push origin main
```

Si llegaron más commits remotos, integrarlos y repetir las verificaciones afectadas. No hacer push forzado ni resolver conflictos aceptando todo automáticamente. La integración realizada tomó `ca25dd5` como punta remota; un `fetch` posterior puede detectar cambios nuevos.

La ejecución validada está en el esquema de QA indicado en `docs/validacion.md`. El push publica el repositorio; para actualizar la instancia histórica de Databricks hay que seguir la migración y el full refresh documentados en `docs/operacion.md`, usando el estado del responsable del despliegue compartido.

La presentación y el guion se prepararán después. Esta entrega no contiene esos materiales.
