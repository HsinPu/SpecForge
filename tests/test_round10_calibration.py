from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round10CalibrationTests(unittest.TestCase):

    def test_scan_project_does_not_treat_flask_script_manage_py_as_django(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text("Flask==3.0.0\nFlask-Script==2.0.6\n", encoding="utf-8")
            (root / "manage.py").write_text(
                """
from flask_script import Manager

from app import create_app

manager = Manager(create_app)

if __name__ == "__main__":
    manager.run()
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("flask", frameworks)
            self.assertNotIn("django", frameworks)

    def test_scan_project_detects_query_clients_openapi_workers_and_k8s_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "react": "^19.0.0",
    "@tanstack/react-query": "^5.0.0",
    "axios": "^1.0.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            src = root / "src" / "repositories"
            src.mkdir(parents=True)
            (src / "articlesRepository.ts").write_text(
                """
import apiClient from './apiClient';

export const getArticle = async (slug: string) => {
  return await apiClient({
    method: 'get',
    url: `/articles/${slug}`,
  });
};

export const createArticle = async () => {
  return await apiClient({
    method: 'post',
    url: '/articles',
  });
};
""".strip()
                + "\n",
                encoding="utf-8",
            )
            queries = root / "src" / "queries"
            queries.mkdir()
            (queries / "articles.query.ts").write_text(
                """
import { useMutation, useQuery } from '@tanstack/react-query';
import { createArticle, getArticle } from '../repositories/articlesRepository';

export const useArticleQuery = (slug: string) =>
  useQuery({ queryKey: ['article', slug], queryFn: () => getArticle(slug) });

export const useCreateArticleMutation = () => useMutation(createArticle);
""".strip()
                + "\n",
                encoding="utf-8",
            )
            pages = root / "src" / "pages"
            pages.mkdir()
            (pages / "home.loader.ts").write_text(
                """
import { getGetArticlesQueryOptions } from '~shared/api/generated/fetch/articles/articles';
import { queryClient } from '~shared/api/queryClient';

export async function homePageLoader() {
  return queryClient.fetchQuery(getGetArticlesQueryOptions({ limit: 20 }));
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            api = root / "api"
            api.mkdir()
            (api / "openapi.yaml").write_text(
                """
openapi: 3.0.0
info:
  title: Demo API
  version: 1.0.0
paths:
  /articles:
    post:
      operationId: createArticle
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ArticleInput'
      responses:
        '201':
          description: Created
        '400':
          description: Invalid input
  /articles/{slug}:
    get:
      operationId: getArticle
      parameters:
        - name: slug
          in: path
          required: true
      responses:
        '200':
          description: OK
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (api / "ping.json").write_text(
                """
{
  "openapi": "3.0.0",
  "info": { "title": "Ping", "version": "1.0.0" },
  "paths": {
    "/ping": {
      "get": {
        "operationId": "ping",
        "responses": {
          "200": { "description": "OK" }
        }
      }
    }
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            project = root / "project"
            (project / "core").mkdir(parents=True)
            (project / "requirements.txt").write_text("Django==5.0\ncelery==5.4.0\n", encoding="utf-8")
            (project / "core" / "tasks.py").write_text(
                """
from celery import shared_task


@shared_task
def send_email_report():
    return "sent"
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "docker-compose.yml").write_text(
                """
services:
  celery:
    image: python:3.13
    command: celery -A core worker -l info
    environment:
      - DJANGO_SETTINGS_MODULE=core.settings
""".strip()
                + "\n",
                encoding="utf-8",
            )

            chart = root / "deploy" / "chart" / "templates"
            chart.mkdir(parents=True)
            (chart.parent / "Chart.yaml").write_text(
                """
apiVersion: v2
name: demo
version: 0.1.0
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (chart / "deployment.yaml").write_text(
                """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo-api
spec:
  template:
    spec:
      containers:
        - name: demo-api
          image: demo/api:latest
          ports:
            - containerPort: 8080
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("tanstack-query", frameworks)
            self.assertIn("openapi", frameworks)
            self.assertIn("celery", frameworks)
            self.assertIn("helm", frameworks)
            self.assertIn("kubernetes", frameworks)

            dependencies = {(dependency.source, dependency.name) for dependency in facts.dependencies}
            self.assertIn(("project/requirements.txt", "celery==5.4.0"), dependencies)

            api_calls = {(call.method, call.endpoint, call.client) for call in facts.api_calls}
            self.assertIn(("GET", "/articles/:slug", "apiClient"), api_calls)
            self.assertIn(("POST", "/articles", "apiClient"), api_calls)
            self.assertIn(("GET", "generated:getGetArticlesQueryOptions", "generated-fetch-client"), api_calls)

            state_usages = {(usage.library, usage.name) for usage in facts.state_usages}
            self.assertIn(("tanstack-query", "useQuery"), state_usages)
            self.assertIn(("tanstack-query", "useMutation"), state_usages)

            api_routes = {(route.method, route.path, route.framework) for route in facts.api_routes}
            self.assertIn(("POST", "/articles", "openapi"), api_routes)
            self.assertIn(("GET", "/articles/{slug}", "openapi"), api_routes)
            self.assertIn(("GET", "/ping", "openapi"), api_routes)

            contracts = {(contract.method, contract.path): contract for contract in facts.api_contracts}
            self.assertEqual(contracts[("POST", "/articles")].request_body, "requestBody")
            self.assertIn("responses:201,400", contracts[("POST", "/articles")].response_type or "")

            runtime_kinds = {config.kind for config in facts.runtime_configs}
            self.assertIn("celery-worker", runtime_kinds)
            self.assertIn("docker-compose", runtime_kinds)
            self.assertIn("helm-chart", runtime_kinds)
            self.assertIn("kubernetes-manifest", runtime_kinds)
            self.assertIn("openapi-spec", runtime_kinds)


if __name__ == "__main__":
    unittest.main()
