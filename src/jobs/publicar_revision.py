# Databricks notebook source
"""Publicación de la cola después de la compuerta de calidad."""
from pathlib import Path

from quality_rules import qualified_schema

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "applebees")
schema = qualified_schema(dbutils.widgets.get("catalog"), dbutils.widgets.get("schema"))
query = Path("modelo_revision.sql").read_text().replace("{{schema}}", schema)

# Un solo commit Delta publica todos los scores de la corrida.
spark.sql(f"CREATE OR REPLACE TABLE {schema}.gold_revision_descuentos USING DELTA AS {query}")
print(f"Cola publicada en {schema}.gold_revision_descuentos")
