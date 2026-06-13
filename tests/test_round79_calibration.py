from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round79SaleorCalibrationTests(unittest.TestCase):
    def test_graphql_schema_descriptions_directives_and_root_types_are_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                """
[project]
dependencies = ["Django>=5", "graphene>=3"]
""".strip()
                + "\n",
                encoding="utf-8",
            )
            schema = root / "saleor" / "graphql"
            schema.mkdir(parents=True)
            (schema / "schema.graphql").write_text(
                '''
schema {
  query: RootQuery
  mutation: RootMutation
  subscription: RootSubscription
}

type RootQuery {
  """
  Look up a warehouse by ID.
  """
  warehouse(
    """
    ID of a warehouse.
    """
    id: ID!
  ): Warehouse @doc(category: "Products")

  warehouses(filter: WarehouseFilterInput, first: Int): WarehouseConnection @deprecated(reason: "Use paginated warehouses")
}

type RootMutation {
  productCreate(input: ProductInput!): ProductCreate @doc(category: "Products")
}

type RootSubscription @doc(category: "Events") {
  event(channels: [String!]): Event
}
'''.strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.method, route.path, route.response_type) for route in facts.api_routes}
            self.assertIn(("QUERY", "/graphql#Query.warehouse", "Warehouse"), routes)
            self.assertIn(("QUERY", "/graphql#Query.warehouses", "WarehouseConnection"), routes)
            self.assertIn(("MUTATION", "/graphql#Mutation.productCreate", "ProductCreate"), routes)
            self.assertIn(("SUBSCRIPTION", "/graphql#Subscription.event", "Event"), routes)

            warehouse = next(route for route in facts.api_routes if route.path == "/graphql#Query.warehouse")
            self.assertEqual("RootQuery", warehouse.class_prefix)
            self.assertIn(("id", "ID!", True), {(param.name, param.type, param.required) for param in warehouse.parameters})
            self.assertGreaterEqual(warehouse.evidence.line_start or 0, 10)

            subscription = next(route for route in facts.api_routes if route.path == "/graphql#Subscription.event")
            self.assertIn(
                ("channels", "[String!]", False),
                {(param.name, param.type, param.required) for param in subscription.parameters},
            )

    def test_django_models_are_data_models_and_semgrep_or_migrations_do_not_become_ml_pipelines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                """
[project]
dependencies = ["Django>=5", "torch>=2"]
""".strip()
                + "\n",
                encoding="utf-8",
            )
            account = root / "saleor" / "account"
            account.mkdir(parents=True)
            (account / "models.py").write_text(
                """
from django.db import models

class Customer(models.Model):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=256, blank=True)
    group = models.ForeignKey("Group", null=True, on_delete=models.CASCADE)

class Group(models.Model):
    name = models.CharField(max_length=128)
""".strip()
                + "\n",
                encoding="utf-8",
            )
            migrations = account / "migrations"
            migrations.mkdir()
            (migrations / "0001_initial.py").write_text(
                """
from django.db import migrations

def forwards(apps, schema_editor):
    customer = apps.get_model("account", "Customer")()
    customer.save()

class Migration(migrations.Migration):
    operations = [migrations.CreateModel(name="Customer", fields=[])]
""".strip()
                + "\n",
                encoding="utf-8",
            )
            semgrep = root / ".semgrep" / "correctness"
            semgrep.mkdir(parents=True)
            (semgrep / "django-rule.py").write_text(
                """
def test_using_default_token_generator():
    user.save()

def validate_address():
    return True
""".strip()
                + "\n",
                encoding="utf-8",
            )
            management = account / "management" / "commands"
            management.mkdir(parents=True)
            (management / "createsuperuser.py").write_text(
                """
class Command:
    def handle(self, **options):
        return "User {} created".format(options["email"])
""".strip()
                + "\n",
                encoding="utf-8",
            )
            ml = root / "training"
            ml.mkdir()
            (ml / "model.py").write_text(
                """
import torch
from torch import nn

class FraudModel(nn.Module):
    pass

def train():
    pass

def evaluate():
    pass
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            models = {model.name: model for model in facts.data_models}
            self.assertEqual("django-model", models["Customer"].kind)
            self.assertIn("email:EmailField", models["Customer"].fields)
            self.assertIn("first_name:CharField", models["Customer"].fields)
            self.assertIn("group:ForeignKey", models["Customer"].fields)
            self.assertIn("unique:email", models["Customer"].annotations)
            self.assertIn("blank:first_name", models["Customer"].annotations)
            self.assertIn("relationship:group:ForeignKey:Group", models["Customer"].annotations)

            data_layers = {(fact.path, fact.kind) for fact in facts.data_layers}
            self.assertIn(("saleor/account/migrations/0001_initial.py", "django-migration"), data_layers)
            self.assertIn(("training/model.py", "ml-pipeline"), data_layers)
            self.assertNotIn((".semgrep/correctness/django-rule.py", "ml-pipeline"), data_layers)
            self.assertNotIn(("saleor/account/migrations/0001_initial.py", "ml-pipeline"), data_layers)
            self.assertNotIn(("saleor/account/management/commands/createsuperuser.py", "python-data-pipeline"), data_layers)


if __name__ == "__main__":
    unittest.main()
