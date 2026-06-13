from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round28CalibrationTests(unittest.TestCase):

    def test_scan_project_composes_django_includes_and_contract_hints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text(
                "Django==5.0\ndjangorestframework==3.15\n",
                encoding="utf-8",
            )
            (root / "config").mkdir()
            (root / "config" / "urls.py").write_text(
                """
\"\"\"
Example only:

urlpatterns = [
    path("docs-only/", include("accounts.urls")),
]
\"\"\"
from django.urls import include, path

urlpatterns = [
    path("api/", include("accounts.urls")),
]
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "accounts").mkdir()
            (root / "accounts" / "urls.py").write_text(
                """
from django.urls import include, path, re_path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register(r"users", UserViewSet)

detail_urls = [
    path("profile/", views.profile),
    path("<int:item_id>/activity/", views.activity),
]

urlpatterns = [
    path("health/", views.health),
    path("users/<uuid:code>/", include(detail_urls)),
    path("router/", include(router.urls)),
    re_path(r"^legacy/(?P<slug>[-\\w]+)/$", views.legacy),
]
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "accounts" / "views.py").write_text(
                """
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework import status


def health(request):
    expand = request.GET.get("expand")
    return JsonResponse({"ok": True, "expand": expand}, status=200)


def profile(request, code):
    name = request.POST.get("name")
    return JsonResponse({"code": str(code), "name": name})


def activity(request, code, item_id):
    payload = request.data
    return Response({"id": item_id, "payload": payload}, status=status.HTTP_201_CREATED)


def legacy(request, slug):
    return JsonResponse({"slug": slug})
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.framework, route.kind, route.path) for route in facts.api_routes}
            self.assertIn(("django", "django-mounted-route", "/api/health"), routes)
            self.assertIn(("django", "django-mounted-route", "/api/users/<uuid:code>/profile"), routes)
            self.assertIn(
                ("django", "django-mounted-route", "/api/users/<uuid:code>/<int:item_id>/activity"),
                routes,
            )
            self.assertIn(("django", "django-mounted-route", "/api/legacy/:slug"), routes)
            self.assertIn(("drf", "drf-mounted-router-route", "/api/router/users"), routes)

            route_paths = {route.path for route in facts.api_routes}
            self.assertNotIn("/health/", route_paths)
            self.assertNotIn("/profile/", route_paths)
            self.assertNotIn("/router/users", route_paths)
            self.assertNotIn("/users", route_paths)
            self.assertNotIn("/docs-only/health/", route_paths)

            contracts = {(contract.framework, contract.path): contract for contract in facts.api_contracts}
            health = contracts[("django", "/api/health")]
            self.assertIn("query:request.GET.expand", health.request_hints)
            self.assertIn("response:JsonResponse", health.response_hints)
            self.assertIn("200", health.status_codes)

            activity = contracts[("django", "/api/users/<uuid:code>/<int:item_id>/activity")]
            self.assertIn("path:code", activity.request_hints)
            self.assertIn("path:item_id", activity.request_hints)
            self.assertIn("body:request.data", activity.request_hints)
            self.assertIn("response:Response", activity.response_hints)
            self.assertIn("201_CREATED", activity.status_codes)
            self.assertNotIn("path:uuid", activity.request_hints)
            self.assertNotIn("path:int", activity.request_hints)

            legacy = contracts[("django", "/api/legacy/:slug")]
            self.assertIn("path:slug", legacy.request_hints)


if __name__ == "__main__":
    unittest.main()
