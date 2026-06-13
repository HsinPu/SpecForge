from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round83SaleorCalibrationTests(unittest.TestCase):
    def test_django_graphql_entrypoints_runtime_and_test_map_noise_are_calibrated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                """
[project]
name = "demo-saleor-like"
dependencies = [
  "django>=5",
  "graphene<3",
  "celery>=5",
  "pytest>=8",
]
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "manage.py").write_text(
                """
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "saleor.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
""".strip()
                + "\n",
                encoding="utf-8",
            )
            saleor = root / "saleor"
            saleor.mkdir()
            (saleor / "__init__.py").write_text("", encoding="utf-8")
            (saleor / "settings.py").write_text("INSTALLED_APPS = []\n", encoding="utf-8")
            (saleor / "views.py").write_text(
                "def handle_plugin_per_channel_webhook(request, channel_slug, plugin_id): pass\n",
                encoding="utf-8",
            )
            (saleor / "urls.py").write_text(
                """
from django.urls import re_path

from . import views

urlpatterns = [
    re_path(
        r"^plugins/channel/(?P<channel_slug>[.0-9A-Za-z_\\-]+)/"
        r"(?P<plugin_id>[.0-9A-Za-z_\\-]+)/",
        views.handle_plugin_per_channel_webhook,
    ),
]
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (saleor / "celeryconf.py").write_text(
                """
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "saleor.settings")
app = Celery("saleor")
app.config_from_object("django.conf:settings", namespace="CELERY")
""".strip()
                + "\n",
                encoding="utf-8",
            )
            asgi = saleor / "asgi"
            asgi.mkdir()
            (asgi / "__init__.py").write_text(
                """
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "saleor.settings")
application = get_asgi_application()
""".strip()
                + "\n",
                encoding="utf-8",
            )
            account = saleor / "account"
            account.mkdir()
            (account / "__init__.py").write_text("", encoding="utf-8")
            (account / "models.py").write_text(
                """
from django.db import models

class Customer(models.Model):
    email = models.EmailField()

def validate_customer(customer):
    customer.save()
""".strip()
                + "\n",
                encoding="utf-8",
            )
            graphql = saleor / "graphql"
            graphql.mkdir()
            (graphql / "schema.graphql").write_text(
                """
type Query {
  webhook(id: ID!): Webhook
}

type Webhook {
  id: ID!
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            semgrep = root / ".semgrep" / "correctness" / "django"
            semgrep.mkdir(parents=True)
            (semgrep / "django-no-default-token-generator.py").write_text(
                "def test_using_default_token_generator():\n    pass\n",
                encoding="utf-8",
            )
            tests = account / "tests"
            fixtures = tests / "fixtures"
            cassettes = tests / "cassettes"
            fixtures.mkdir(parents=True)
            cassettes.mkdir()
            (tests / "__init__.py").write_text("", encoding="utf-8")
            (fixtures / "user.py").write_text("WEBHOOK_FIXTURE = 'webhook'\n", encoding="utf-8")
            (cassettes / "webhook.yaml").write_text("request: webhook\n", encoding="utf-8")
            (tests / "asgi_test_utils.py").write_text("WEBHOOK_HELPER = 'webhook'\n", encoding="utf-8")
            (tests / "test_account.py").write_text(
                """
def test_webhook_query(api_client):
    query = '''
    query {
      webhook(id: "1") { id }
    }
    '''
    assert query
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (tests / "test_validators.py").write_text(
                "import pytest\n\n\ndef test_validation_error():\n    assert pytest.raises\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            entrypoints = {(item.kind, item.path, item.command) for item in facts.entrypoints}
            self.assertIn(("django-manage", "manage.py", "python manage.py runserver"), entrypoints)
            self.assertIn(("django-asgi", "saleor/asgi/__init__.py", "uvicorn saleor.asgi:application"), entrypoints)
            self.assertIn(("celery-app", "saleor/celeryconf.py", "celery -A saleor.celeryconf:app worker -l info"), entrypoints)

            commands = {item.name for item in facts.commands}
            self.assertIn("python manage.py runserver", commands)
            self.assertIn("python manage.py migrate", commands)
            self.assertIn("pytest", commands)
            self.assertIn("celery -A saleor.celeryconf:app worker -l info", commands)

            runtime_kinds_by_path = {(item.path, item.kind) for item in facts.runtime_configs}
            self.assertNotIn(("saleor/account/models.py", "ml-source"), runtime_kinds_by_path)
            self.assertNotIn((".semgrep/correctness/django/django-no-default-token-generator.py", "ml-source"), runtime_kinds_by_path)

            routes = {(item.framework, item.kind, item.path) for item in facts.api_routes}
            self.assertIn(
                (
                    "django",
                    "django-regex-route",
                    "/plugins/channel/:channel_slug/:plugin_id",
                ),
                routes,
            )

            maps = {item.test_path: item for item in facts.test_maps}
            self.assertIn("saleor/account/tests/test_account.py", maps)
            self.assertEqual("api-route", maps["saleor/account/tests/test_account.py"].target_kind)
            self.assertEqual("QUERY /graphql#Query.webhook", maps["saleor/account/tests/test_account.py"].target)
            self.assertEqual("unmatched", maps["saleor/account/tests/test_validators.py"].target_kind)
            self.assertNotIn("saleor/account/tests/__init__.py", maps)
            self.assertNotIn("saleor/account/tests/fixtures/user.py", maps)
            self.assertNotIn("saleor/account/tests/cassettes/webhook.yaml", maps)
            self.assertNotIn("saleor/account/tests/asgi_test_utils.py", maps)


if __name__ == "__main__":
    unittest.main()
