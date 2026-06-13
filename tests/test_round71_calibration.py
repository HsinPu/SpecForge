from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round71DjangoTemplateCalibrationTests(unittest.TestCase):
    def test_drf_router_modules_and_django_ninja_routes_are_mounted_without_fastapi_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text(
                "Django==5.0\ndjangorestframework==3.15\ndjango-ninja==1.3.0\n",
                encoding="utf-8",
            )
            config = root / "config"
            api_dir = root / "project" / "users" / "api"
            template_dir = root / "{{cookiecutter.project_slug}}" / "{{cookiecutter.project_slug}}" / "templates" / "pages"
            config.mkdir()
            api_dir.mkdir(parents=True)
            template_dir.mkdir(parents=True)

            (config / "urls.py").write_text(
                """
from django.urls import include, path
from .api import api

urlpatterns = [
    path("api/", include("config.api_router")),
    path("ninja/", api.urls),
]
""".strip(),
                encoding="utf-8",
            )
            (config / "api_router.py").write_text(
                """
from rest_framework.routers import DefaultRouter
from project.users.api.views import UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet)

urlpatterns = router.urls
""".strip(),
                encoding="utf-8",
            )
            (config / "api.py").write_text(
                """
from ninja import NinjaAPI

api = NinjaAPI()
api.add_router("/users/", "project.users.api.views.router")
""".strip(),
                encoding="utf-8",
            )
            (api_dir / "views.py").write_text(
                """
from ninja import Router
from rest_framework.viewsets import GenericViewSet

router = Router(tags=["users"])

class UserViewSet(GenericViewSet):
    pass

class UserSchema:
    pass

@router.get("/me/", response=UserSchema)
def retrieve_current_user(request):
    return request.user
""".strip(),
                encoding="utf-8",
            )
            (template_dir / "home.html").write_text(
                """
{% extends "base.html" %}
{% block title %}Home{% endblock title %}
<a href="{% url 'users:detail' request.user.username %}">Profile</a>
""".strip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            self.assertIn("django-ninja", {framework.name for framework in facts.frameworks})
            routes = {(route.framework, route.kind, route.method, route.path) for route in facts.api_routes}
            self.assertIn(("drf", "drf-mounted-router-route", "ANY", "/api/users"), routes)
            self.assertIn(("django-ninja", "django-ninja-mounted-route", "GET", "/ninja/users/me/"), routes)
            self.assertNotIn("fastapi", {route.framework for route in facts.api_routes})

            ninja = next(route for route in facts.api_routes if route.framework == "django-ninja")
            self.assertEqual("retrieve_current_user", ninja.handler)
            self.assertEqual("UserSchema", ninja.response_type)
            self.assertIn("child=project/users/api/views.py", ninja.evidence.note or "")

            pages = {(page.route, page.template_engine, page.path) for page in facts.pages}
            self.assertIn(
                (
                    "/pages/home",
                    "django-template",
                    "{{cookiecutter.project_slug}}/{{cookiecutter.project_slug}}/templates/pages/home.html",
                ),
                pages,
            )


if __name__ == "__main__":
    unittest.main()
