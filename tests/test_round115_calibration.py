from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round115DjangoRealworldCalibrationTests(unittest.TestCase):
    def test_django_regex_routes_and_inherited_models_are_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            conduit = root / "conduit"
            articles = conduit / "apps" / "articles"
            core = conduit / "apps" / "core"
            auth = conduit / "apps" / "authentication"
            for path in (articles, core, auth):
                path.mkdir(parents=True)

            (conduit / "urls.py").write_text(
                """
from django.conf.urls import include, url

urlpatterns = [
    url(r'^api/', include('conduit.apps.articles.urls', namespace='articles')),
]
""".lstrip(),
                encoding="utf-8",
            )
            (articles / "urls.py").write_text(
                """
from django.conf.urls import include, url
from rest_framework.routers import DefaultRouter
from .views import ArticleViewSet, ArticlesFeedAPIView, CommentsDestroyAPIView

router = DefaultRouter(trailing_slash=False)
router.register(r'articles', ArticleViewSet)

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'^articles/feed/?$', ArticlesFeedAPIView.as_view()),
    url(
        r'^articles/(?P<article_slug>[-\\w]+)/comments/(?P<comment_pk>[\\d]+)/?$',
        CommentsDestroyAPIView.as_view()
    ),
]
""".lstrip(),
                encoding="utf-8",
            )
            (core / "models.py").write_text(
                """
from django.db import models

class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
""".lstrip(),
                encoding="utf-8",
            )
            (articles / "models.py").write_text(
                """
from django.db import models
from conduit.apps.core.models import TimestampedModel

class Article(TimestampedModel):
    title = models.CharField(db_index=True, max_length=255)

    author = models.ForeignKey(
        'profiles.Profile', on_delete=models.CASCADE, related_name='articles'
    )
    tags = models.ManyToManyField(
        'articles.Tag', related_name='articles'
    )

class Tag(TimestampedModel):
    slug = models.SlugField(db_index=True, unique=True)
""".lstrip(),
                encoding="utf-8",
            )
            (auth / "models.py").write_text(
                """
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from conduit.apps.core.models import TimestampedModel

class User(AbstractBaseUser, PermissionsMixin, TimestampedModel):
    username = models.CharField(db_index=True, max_length=255, unique=True)

    email = models.EmailField(db_index=True, unique=True)
""".lstrip(),
                encoding="utf-8",
            )
            migration_dir = articles / "migrations"
            migration_dir.mkdir()
            (migration_dir / "0002_tags.py").write_text(
                """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name='article',
            name='tags',
            field=models.ManyToManyField(related_name='articles', to='articles.Tag'),
        )
    ]
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.method, route.path, route.framework): route for route in facts.api_routes}
            self.assertIn(("ANY", "/api/articles", "drf"), routes)
            self.assertIn(("ANY", "/api/articles/feed", "django"), routes)
            self.assertIn(("ANY", "/api/articles/:article_slug/comments/:comment_pk", "django"), routes)
            self.assertFalse(any("^" in route.path or "(?P" in route.path for route in facts.api_routes))
            comment_route = routes[("ANY", "/api/articles/:article_slug/comments/:comment_pk", "django")]
            self.assertEqual(["article_slug", "comment_pk"], [param.name for param in comment_route.parameters])

            models = {(model.name, model.kind): model for model in facts.data_models}
            self.assertIn(("Article", "django-model"), models)
            self.assertIn(("Tag", "django-model"), models)
            self.assertIn(("User", "django-model"), models)
            self.assertNotIn(("Migration", "django-model"), models)
            article = models[("Article", "django-model")]
            self.assertIn("title:CharField", article.fields)
            self.assertIn("author:ForeignKey", article.fields)
            self.assertIn("tags:ManyToManyField", article.fields)
            self.assertIn("relationship:author:ForeignKey:profiles.Profile", article.annotations)
            self.assertIn("relationship:tags:ManyToManyField:articles.Tag", article.annotations)
            self.assertIn("email:EmailField", models[("User", "django-model")].fields)


if __name__ == "__main__":
    unittest.main()
