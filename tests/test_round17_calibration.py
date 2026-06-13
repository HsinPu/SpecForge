from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round17CalibrationTests(unittest.TestCase):

    def test_scan_project_detects_data_engineering_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            (root / "requirements.txt").write_text(
                "\n".join(
                    [
                        "apache-airflow",
                        "dbt-core",
                        "dbt-duckdb",
                        "prefect",
                        "dagster",
                        "kedro",
                        "great-expectations",
                        "pyspark",
                        "delta-spark",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            (root / "dbt_project.yml").write_text(
                """
name: analytics
profile: analytics
model-paths: ["models"]
seed-paths: ["seeds"]
macro-paths: ["macros"]
""".strip()
                + "\n",
                encoding="utf-8",
            )
            models = root / "models"
            models.mkdir()
            (models / "orders.sql").write_text(
                """
{{ config(materialized='table') }}

select *
from {{ ref('stg_orders') }}
join {{ source('stripe', 'payments') }} using (order_id)
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (models / "schema.yml").write_text(
                """
version: 2
models:
  - name: orders
    columns:
      - name: order_id
    tests:
      - unique
sources:
  - name: stripe
    tables:
      - name: payments
        columns:
          - name: payment_id
""".strip()
                + "\n",
                encoding="utf-8",
            )
            macros = root / "macros"
            macros.mkdir()
            (macros / "cents_to_dollars.sql").write_text(
                """
{% macro cents_to_dollars(column_name) %}
  ({{ column_name }} / 100)
{% endmacro %}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            dags = root / "dags"
            dags.mkdir()
            astro = root / ".astro"
            astro.mkdir()
            (astro / "test_dag_integrity_default.py").write_text(
                "from airflow.models import DagBag\n\ndef test_dagbag():\n    assert DagBag\n",
                encoding="utf-8",
            )
            (dags / "daily_orders.py").write_text(
                """
from airflow import DAG
from airflow.operators.python import PythonOperator

with DAG(dag_id="daily_orders", schedule="@daily") as dag:
    extract = PythonOperator(task_id="extract_orders", python_callable=lambda: None)
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (dags / "decorated_daily.py").write_text(
                """
from airflow.decorators import dag, task

@dag(schedule="@daily")
def decorated_daily():
    @task
    def transform_orders():
        return "ok"

    transform_orders()

decorated_daily()
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (dags / "orders_operator.py").write_text(
                """
from airflow.models import BaseOperator

class WaitForOrdersOperator(BaseOperator):
    pass
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "prefect_flow.py").write_text(
                """
from prefect import flow, task

@task
def extract_orders():
    return "orders.csv"

@flow
def orders_flow():
    return extract_orders()
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "prefect.yaml").write_text(
                """
name: analytics-flows
deployments:
  - name: orders-deployment
    entrypoint: prefect_flow.py:orders_flow
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "dagster_defs.py").write_text(
                """
from dagster import Definitions, asset, job, op

@asset
def orders_asset():
    return 1

@op
def clean_orders():
    return orders_asset()

@job
def orders_job():
    clean_orders()

defs = Definitions(assets=[orders_asset], jobs=[orders_job])
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "dagster.yaml").write_text("python_file: dagster_defs.py\n", encoding="utf-8")

            conf = root / "conf" / "base"
            conf.mkdir(parents=True)
            (conf / "catalog.yml").write_text(
                """
orders:
  type: pandas.CSVDataset
  filepath: data/01_raw/orders.csv
""".strip()
                + "\n",
                encoding="utf-8",
            )
            package = root / "src" / "demo"
            package.mkdir(parents=True)
            (package / "pipeline.py").write_text(
                """
from kedro.pipeline import Pipeline, node

def build_orders():
    return "orders"

pipeline = Pipeline([
    node(build_orders, inputs=None, outputs="orders")
])
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "great_expectations.yml").write_text(
                """
config_version: 3.0
datasources:
  warehouse:
    class_name: Datasource
""".strip()
                + "\n",
                encoding="utf-8",
            )

            notebook = {
                "cells": [
                    {
                        "cell_type": "code",
                        "source": [
                            "from pyspark.sql import SparkSession\n",
                            "spark = SparkSession.builder.getOrCreate()\n",
                            "df = spark.read.format('delta').load('/lake/orders')\n",
                            "df.write.format('delta').save('/lake/curated/orders')\n",
                        ],
                    }
                ],
                "metadata": {"kernelspec": {"name": "python3", "language": "python"}},
            }
            (root / "notebooks").mkdir()
            (root / "notebooks" / "delta_orders.ipynb").write_text(json.dumps(notebook), encoding="utf-8")

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertTrue(
                {
                    "airflow",
                    "dagster",
                    "dbt",
                    "delta-lake",
                    "great-expectations",
                    "jupyter-notebook",
                    "kedro",
                    "prefect",
                    "pyspark",
                }
                <= frameworks
            )

            data_kinds = {fact.kind for fact in facts.data_layers}
            self.assertTrue({"dbt-project", "dbt-macro", "dbt-model", "dbt-yaml", "notebook", "python-data-pipeline"} <= data_kinds)
            data_details = {detail for fact in facts.data_layers for detail in fact.details}
            self.assertIn("ref:stg_orders", data_details)
            self.assertIn("source:stripe.payments", data_details)
            self.assertIn("source:stripe", data_details)
            self.assertIn("source-table:stripe.payments", data_details)
            self.assertIn("macro:cents_to_dollars", data_details)
            self.assertNotIn("model:order_id", data_details)
            self.assertNotIn("source:payment_id", data_details)
            self.assertIn("spark-format:delta", data_details)
            self.assertIn("dataset:orders", {value for fact in facts.runtime_configs for value in fact.values})

            runtime_kinds = {fact.kind for fact in facts.runtime_configs}
            self.assertTrue(
                {
                    "airflow-dag",
                    "airflow-operator",
                    "dagster-code",
                    "dagster-config",
                    "dbt-project",
                    "great-expectations-config",
                    "kedro-catalog",
                    "kedro-pipeline",
                    "notebook",
                    "prefect-config",
                    "prefect-flow",
                }
                <= runtime_kinds
            )
            runtime_values = {value for fact in facts.runtime_configs for value in fact.values}
            self.assertIn("dag:daily_orders", runtime_values)
            self.assertIn("dag:decorated_daily", runtime_values)
            self.assertIn("task:extract_orders", runtime_values)
            self.assertIn("task:transform_orders", runtime_values)
            self.assertIn("operator-class:WaitForOrdersOperator", runtime_values)
            self.assertIn("flow:orders_flow", runtime_values)
            self.assertIn("asset:orders_asset", runtime_values)
            self.assertIn("node:build_orders", runtime_values)
            runtime_paths = {fact.path for fact in facts.runtime_configs}
            self.assertNotIn(".astro/test_dag_integrity_default.py", runtime_paths)


if __name__ == "__main__":
    unittest.main()
