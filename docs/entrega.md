# Archivos para el commit y push a main

La entrega está integrada en la raíz del repositorio; no hay una segunda copia de código que deba elegirse manualmente. No se hizo commit ni push durante la revisión.

## Incluir

Todos los cambios versionables bajo estas rutas:

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

## Revisar y guardar

Desde la raíz:

```bash
python3 scripts/validate_local.py
git status --short
git diff --check
git diff --stat
# Todos los archivos versionables de este cambio forman parte de la entrega:
git add .gitignore README.md databricks.yml .github resources src exploration tests scripts validation docs
git diff --cached --stat
git diff --cached --check
git commit -m "Fortalece pipeline, calidad y validación de Fase 2"
```

En la comprobación de esta revisión, `origin/main` y el HEAD local coincidían en `d0410d7c3adb4f50e40fb16c2197a7e839cee190`. Antes de publicar en `main`, volver a comprobar si hubo cambios remotos mientras se trabajaba. Si los hay, integrarlos y repetir las verificaciones afectadas. No hacer push forzado ni resolver conflictos aceptando todo automáticamente. Si el remoto sigue en la misma base, ejecutar `git push origin main`.

La ejecución validada está en el esquema de QA indicado en `docs/validacion.md`. El push publica el repositorio; para actualizar la instancia histórica de Databricks hay que seguir la migración y el full refresh documentados en `docs/operacion.md`, usando el estado del responsable del despliegue compartido.

La presentación y el guion se prepararán después. Esta entrega no contiene esos materiales.
