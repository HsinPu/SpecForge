from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.gaps import detect_gaps
from specforge.renderers import write_spec_bundle
from specforge.scanner import scan_project
from specforge.trace import build_trace_claims


class ScannerTests(unittest.TestCase):

    def test_scan_project_detects_full_stack_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "express": "^4.0.0",
    "next": "^14.0.0",
    "react": "^18.0.0",
    "vite": "^5.0.0"
  }
}
""".strip(),
                encoding="utf-8",
            )
            (root / "pyproject.toml").write_text(
                """
[project]
name = "api"
dependencies = ["fastapi"]
""".strip(),
                encoding="utf-8",
            )
            (root / "pom.xml").write_text(
                """
<project>
  <packaging>war</packaging>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
      <groupId>jakarta.servlet</groupId>
      <artifactId>jakarta.servlet-api</artifactId>
      <scope>provided</scope>
    </dependency>
  </dependencies>
</project>
""".strip(),
                encoding="utf-8",
            )

            (root / "src").mkdir()
            (root / "src" / "server.ts").write_text(
                """
import express from 'express';
const app = express();
app.get('/health', healthHandler);
""".strip(),
                encoding="utf-8",
            )
            (root / "api").mkdir()
            (root / "api" / "main.py").write_text(
                """
from fastapi import FastAPI
app = FastAPI()

@app.post("/items")
def create_item():
    return {}
""".strip(),
                encoding="utf-8",
            )
            spring_dir = root / "src" / "main" / "java" / "com" / "example"
            spring_dir.mkdir(parents=True)
            (spring_dir / "UserController.java").write_text(
                """
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api")
class UserController {
  @GetMapping("/users/{id}")
  public UserDto user(@PathVariable("id") String id, @RequestParam(required = false) String expand) {
    return new UserDto();
  }

  @PostMapping("/users")
  public UserDto create(@RequestBody UserDto request) {
    return request;
  }
}
""".strip(),
                encoding="utf-8",
            )
            (spring_dir / "UserDto.java").write_text(
                """
class UserDto {
  private String id;
  private String name;
}
""".strip(),
                encoding="utf-8",
            )
            (spring_dir / "UserEntity.java").write_text(
                """
import jakarta.persistence.Entity;
import jakarta.persistence.Id;

@Entity
class UserEntity {
  @Id
  private Long id;
  private String name;
}
""".strip(),
                encoding="utf-8",
            )
            (spring_dir / "UserRepository.java").write_text(
                """
import org.springframework.data.jpa.repository.JpaRepository;

interface UserRepository extends JpaRepository<UserEntity, Long> {}
""".strip(),
                encoding="utf-8",
            )
            (spring_dir / "UserService.java").write_text(
                """
import org.springframework.stereotype.Service;

@Service
class UserService {
  public UserDto findUser(String id) { return new UserDto(); }
}
""".strip(),
                encoding="utf-8",
            )
            (spring_dir / "LegacyUsersServlet.java").write_text(
                """
import jakarta.servlet.annotation.WebServlet;
import jakarta.servlet.http.HttpServlet;

@WebServlet("/legacy/annotated-users")
class LegacyUsersServlet extends HttpServlet {}
""".strip(),
                encoding="utf-8",
            )
            web_inf_dir = root / "src" / "main" / "webapp" / "WEB-INF"
            web_inf_dir.mkdir(parents=True)
            (web_inf_dir / "web.xml").write_text(
                """
<web-app>
  <servlet>
    <servlet-name>legacyUsers</servlet-name>
    <servlet-class>com.example.LegacyUsersServlet</servlet-class>
  </servlet>
  <servlet-mapping>
    <servlet-name>legacyUsers</servlet-name>
    <url-pattern>/legacy/users</url-pattern>
  </servlet-mapping>
</web-app>
""".strip(),
                encoding="utf-8",
            )
            (root / "src" / "main" / "webapp" / "users.jsp").write_text(
                """
<%@ taglib prefix="c" uri="http://java.sun.com/jsp/jstl/core" %>
<html>
  <body>
    <form action="/legacy/users" method="post">
      <input name="name" value="${user.name}" />
    </form>
    <a href="/dashboard">Dashboard</a>
    <script src="/static/users.js"></script>
  </body>
</html>
""".strip(),
                encoding="utf-8",
            )

            page_dir = root / "app" / "dashboard"
            page_dir.mkdir(parents=True)
            (page_dir / "page.tsx").write_text(
                """
import React, { useEffect } from 'react';

interface DashboardCardProps {
  userId: string;
  onSelect?: () => void;
}

export function DashboardCard(props: DashboardCardProps) {
  useEffect(() => {}, []);
  fetch('/api/users', { method: 'POST' });
  return <div>{props.userId}</div>;
}
""".strip(),
                encoding="utf-8",
            )
            api_dir = root / "app" / "api" / "users"
            api_dir.mkdir(parents=True)
            (api_dir / "route.ts").write_text(
                """
export function GET() {
  return Response.json([]);
}
""".strip(),
                encoding="utf-8",
            )

            facts = scan_project(root)
            claims = build_trace_claims(facts)
            gaps = detect_gaps(facts)
            spec_out = root / "spec"
            write_spec_bundle(facts, claims, gaps, spec_out)

            self.assertIn("react", {framework.name for framework in facts.frameworks})
            self.assertIn("next", {framework.name for framework in facts.frameworks})
            self.assertIn("express", {framework.name for framework in facts.frameworks})
            self.assertIn("fastapi", {framework.name for framework in facts.frameworks})
            self.assertIn("spring", {framework.name for framework in facts.frameworks})
            self.assertIn("java-web", {framework.name for framework in facts.frameworks})
            self.assertIn("servlet", {framework.name for framework in facts.frameworks})
            self.assertIn("jsp", {framework.name for framework in facts.frameworks})
            self.assertIn("/health", {route.path for route in facts.api_routes})
            self.assertIn("/items", {route.path for route in facts.api_routes})
            self.assertIn("/api/users/{id}", {route.path for route in facts.api_routes})
            self.assertIn("/api/users", {route.path for route in facts.api_routes})
            self.assertIn("/api/users", {route.path for route in facts.api_routes})
            self.assertIn("/legacy/users", {route.path for route in facts.api_routes})
            self.assertIn("/legacy/annotated-users", {route.path for route in facts.api_routes})
            user_route = next(
                route for route in facts.api_routes
                if route.framework == "spring" and route.path == "/api/users/{id}"
            )
            self.assertEqual(user_route.class_prefix, "/api")
            self.assertEqual(user_route.response_type, "UserDto")
            self.assertIn("id", {param.name for param in user_route.parameters})
            self.assertIn("expand", {param.name for param in user_route.parameters})
            create_route = next(
                route for route in facts.api_routes
                if route.framework == "spring" and route.method == "POST" and route.path == "/api/users"
            )
            self.assertEqual(create_route.request_body, "UserDto")
            self.assertIn("UserDto", {model.name for model in facts.data_models})
            self.assertIn("UserEntity", {model.name for model in facts.data_models})
            self.assertIn("UserRepository", {repository.name for repository in facts.repositories})
            self.assertIn("UserService", {service.name for service in facts.services})
            self.assertIn("legacyUsers", {servlet.name for servlet in facts.servlets})
            self.assertIn("LegacyUsersServlet", {servlet.name for servlet in facts.servlets})
            self.assertIn("/users.jsp", {page.route for page in facts.jsp_pages})
            self.assertIn("/api/users/{id}", {contract.path for contract in facts.api_contracts})
            self.assertIn("DashboardCard", {component.name for component in facts.components})
            self.assertIn("/dashboard", {route.route for route in facts.frontend_routes})
            self.assertIn("/api/users", {call.endpoint for call in facts.api_calls})
            self.assertTrue((spec_out / "backend.md").exists())
            self.assertTrue((spec_out / "frontend.md").exists())
            self.assertTrue((spec_out / "api-routes.md").exists())
            self.assertTrue((spec_out / "components.md").exists())
            self.assertTrue((spec_out / "frameworks.md").exists())
            self.assertTrue((spec_out / "java-web.md").exists())
            self.assertTrue((spec_out / "spring.md").exists())
            self.assertTrue((spec_out / "servlets.md").exists())
            self.assertTrue((spec_out / "jsp-pages.md").exists())
            self.assertTrue((spec_out / "data-models.md").exists())
            self.assertTrue((spec_out / "api-contracts.md").exists())
            self.assertIn("/api/users/{id}", (spec_out / "spring.md").read_text(encoding="utf-8"))
            self.assertIn("/legacy/users", (spec_out / "servlets.md").read_text(encoding="utf-8"))
            self.assertIn("/users.jsp", (spec_out / "jsp-pages.md").read_text(encoding="utf-8"))
            self.assertIn("UserEntity", (spec_out / "data-models.md").read_text(encoding="utf-8"))
            self.assertIn("UserDto", (spec_out / "api-contracts.md").read_text(encoding="utf-8"))

    def test_scan_project_detects_static_frontend_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "@reduxjs/toolkit": "^2.0.0",
    "bootstrap": "^5.0.0",
    "pinia": "^3.0.0",
    "react": "^18.0.0",
    "react-router-dom": "^6.0.0",
    "sass": "^1.0.0",
    "tailwindcss": "^4.0.0",
    "vue-router": "^4.0.0",
    "zustand": "^5.0.0"
  }
}
""".strip(),
                encoding="utf-8",
            )
            (root / "tailwind.config.js").write_text("module.exports = {}\n", encoding="utf-8")
            public_dir = root / "public"
            public_dir.mkdir()
            (public_dir / "index.html").write_text(
                """
<!doctype html>
<html>
  <head>
    <title>Login</title>
    <link rel="stylesheet" href="/styles.css">
  </head>
  <body class="tailwind">
    <form action="/login" method="post">
      <input name="email">
      <input name="password">
    </form>
    <a href="/about.html">About</a>
    <img src="/assets/logo.png">
    <script src="/app.js"></script>
    <script>
      fetch("/api/login", { method: "POST" });
    </script>
  </body>
</html>
""".strip(),
                encoding="utf-8",
            )
            (public_dir / "about.html").write_text("<title>About</title>\n", encoding="utf-8")
            (public_dir / "styles.css").write_text(
                """
@import url("/base.css");
:root { --brand: #123456; }
.login-card, #title { background-image: url("/assets/logo.png"); }
""".strip(),
                encoding="utf-8",
            )
            (public_dir / "app.js").write_text(
                """
client.post("/api/profile");
""".strip(),
                encoding="utf-8",
            )
            template_dir = root / "src" / "main" / "resources" / "templates"
            template_dir.mkdir(parents=True)
            (template_dir / "home.html").write_text(
                """
<html xmlns:th="http://www.thymeleaf.org">
  <head><title>Home</title></head>
  <body>
    <form th:action="/search" method="get"><input name="q"></form>
  </body>
</html>
""".strip(),
                encoding="utf-8",
            )
            (template_dir / "report.ftl").write_text("<title>Report</title>\n", encoding="utf-8")
            (template_dir / "card.hbs").write_text("<h1>{{title}}</h1>\n", encoding="utf-8")
            src_dir = root / "src"
            (src_dir / "App.tsx").write_text(
                """
import { useState } from 'react';
import { useSelector } from 'react-redux';
import { create } from 'zustand';
import { Route } from 'react-router-dom';

const useStore = create((set) => ({ count: 0 }));
const routes = [{ path: '/settings' }];

export function App() {
  useState(0);
  useSelector((state) => state.user);
  fetch('/api/settings');
  return <Route path="/settings" element={<div />} />;
}
""".strip(),
                encoding="utf-8",
            )
            (src_dir / "router.ts").write_text(
                """
import { createRouter } from 'vue-router';
import { defineStore } from 'pinia';

const routes = [{ path: '/vue-home' }];
defineStore('session', {});
createRouter({ routes });
""".strip(),
                encoding="utf-8",
            )

            facts = scan_project(root)
            claims = build_trace_claims(facts)
            gaps = detect_gaps(facts)
            spec_out = root / "spec"
            write_spec_bundle(facts, claims, gaps, spec_out)

            self.assertEqual(facts.languages["html"], 3)
            self.assertEqual(facts.languages["css"], 1)
            self.assertIn("static-site", {framework.name for framework in facts.frameworks})
            self.assertIn("thymeleaf", {framework.name for framework in facts.frameworks})
            self.assertIn("freemarker", {framework.name for framework in facts.frameworks})
            self.assertIn("handlebars", {framework.name for framework in facts.frameworks})
            self.assertIn("tailwind", {framework.name for framework in facts.frameworks})
            self.assertIn("bootstrap", {framework.name for framework in facts.frameworks})
            self.assertIn("sass", {framework.name for framework in facts.frameworks})
            self.assertIn("react-router", {framework.name for framework in facts.frameworks})
            self.assertIn("vue-router", {framework.name for framework in facts.frameworks})
            self.assertIn("redux", {framework.name for framework in facts.frameworks})
            self.assertIn("zustand", {framework.name for framework in facts.frameworks})
            self.assertIn("pinia", {framework.name for framework in facts.frameworks})
            self.assertIn("/", {page.route for page in facts.pages})
            self.assertIn("/about", {page.route for page in facts.pages})
            self.assertIn("/report", {page.route for page in facts.pages})
            self.assertIn("/card", {page.route for page in facts.pages})
            self.assertIn("/settings", {route.route for route in facts.frontend_routes})
            self.assertIn("/vue-home", {route.route for route in facts.frontend_routes})
            self.assertIn("/login", {form.action for form in facts.forms})
            self.assertIn("email", {field for form in facts.forms for field in form.fields})
            self.assertIn("/styles.css", {asset.asset_path for asset in facts.assets})
            self.assertIn("/assets/logo.png", {asset.asset_path for asset in facts.assets})
            self.assertIn("login-card", {item for style in facts.styles for item in style.classes})
            self.assertIn("title", {item for style in facts.styles for item in style.ids})
            self.assertIn("--brand", {item for style in facts.styles for item in style.css_variables})
            self.assertIn("/api/login", {call.endpoint for call in facts.api_calls})
            self.assertIn("/api/profile", {call.endpoint for call in facts.api_calls})
            self.assertIn("/api/settings", {call.endpoint for call in facts.api_calls})
            self.assertIn("useState", {usage.name for usage in facts.state_usages})
            self.assertIn("useSelector", {usage.name for usage in facts.state_usages})
            self.assertIn("defineStore", {usage.name for usage in facts.state_usages})
            self.assertTrue(facts.frontend_maps)
            self.assertTrue((spec_out / "pages.md").exists())
            self.assertTrue((spec_out / "forms.md").exists())
            self.assertTrue((spec_out / "assets.md").exists())
            self.assertTrue((spec_out / "styles.md").exists())
            self.assertTrue((spec_out / "state.md").exists())
            self.assertTrue((spec_out / "frontend-map.md").exists())
            self.assertIn("/api/login", (spec_out / "api-calls.md").read_text(encoding="utf-8"))
            self.assertIn("login-card", (spec_out / "styles.md").read_text(encoding="utf-8"))
            self.assertIn("useSelector", (spec_out / "state.md").read_text(encoding="utf-8"))

    def test_scan_project_builds_v2_connected_rebuild_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "scripts": { "build": "vite build", "test": "vitest" },
  "dependencies": {
    "express": "^5.0.0",
    "react": "^19.0.0",
    "axios": "^1.0.0",
    "drizzle-orm": "^0.30.0"
  },
  "devDependencies": { "vite": "^7.0.0" }
}
""".strip(),
                encoding="utf-8",
            )
            (root / ".env.example").write_text(
                "API_URL=\nDATABASE_URL=\nSECRET_SHOULD_NOT_RENDER=value\n",
                encoding="utf-8",
            )
            (root / "Dockerfile").write_text(
                """
FROM python:3.13
EXPOSE 8080
CMD ["python", "-m", "api.main"]
""".strip(),
                encoding="utf-8",
            )
            (root / "docker-compose.yml").write_text(
                """
services:
  web:
    build: .
    ports:
      - "8080:8080"
  db:
    image: postgres:18
""".strip(),
                encoding="utf-8",
            )
            workflow_dir = root / ".github" / "workflows"
            workflow_dir.mkdir(parents=True)
            (workflow_dir / "ci.yml").write_text(
                """
name: ci
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: py -3 -m unittest
""".strip(),
                encoding="utf-8",
            )
            resources_dir = root / "src" / "main" / "resources"
            resources_dir.mkdir(parents=True)
            (resources_dir / "application.yml").write_text(
                """
server:
  port: 9090
spring:
  datasource:
    url: jdbc:postgresql://localhost/app
""".strip(),
                encoding="utf-8",
            )

            src_dir = root / "src"
            src_dir.mkdir(exist_ok=True)
            (src_dir / "UserCard.tsx").write_text(
                """
import React from 'react';

type UserCardProps = { id: string };

export function UserCard(props: UserCardProps) {
  fetch('/api/users/123');
  fetch('/api/profile', { method: 'POST', body: JSON.stringify(props) });
  return <div>{props.id}</div>;
}
""".strip(),
                encoding="utf-8",
            )
            (src_dir / "db.ts").write_text(
                """
import { pgTable, serial } from 'drizzle-orm/pg-core';
export const users = pgTable('users', { id: serial('id') });
""".strip(),
                encoding="utf-8",
            )

            api_dir = root / "api"
            api_dir.mkdir()
            (api_dir / "server.ts").write_text(
                """
import express from 'express';
const app = express();

app.get('/api/users/:id', (req, res) => {
  const id = req.params.id;
  const expand = req.query.expand;
  return res.status(200).json({ id, expand });
});

app.post('/api/profile', (req, res) => {
  const name = req.body.name;
  return res.status(201).json({ name });
});
""".strip(),
                encoding="utf-8",
            )
            (api_dir / "main.py").write_text(
                """
from fastapi import FastAPI, status, HTTPException

app = FastAPI()

class UserBody:
    name: str

@app.get('/api/users/{id}', status_code=status.HTTP_200_OK, response_model=UserBody)
def read_user(id: str, expand: str | None = None):
    if id == '0':
        raise HTTPException(status_code=404)
    return UserBody()
""".strip(),
                encoding="utf-8",
            )
            (api_dir / "flask_app.py").write_text(
                """
from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/api/search/<term>', methods=['GET'])
def search(term):
    q = request.args.get('q')
    data = request.json
    return jsonify({'term': term, 'q': q, 'data': data}), 200
""".strip(),
                encoding="utf-8",
            )
            (api_dir / "models.py").write_text(
                """
from django.db import models
from sqlalchemy import Column, Integer

class Account(Base):
    __tablename__ = 'accounts'
    id = Column(Integer)

class AuditLog(models.Model):
    id = models.IntegerField()
""".strip(),
                encoding="utf-8",
            )

            (root / "schema.prisma").write_text(
                """
datasource db { provider = "postgresql" url = env("DATABASE_URL") }
model User { id Int @id name String }
""".strip(),
                encoding="utf-8",
            )
            migration_dir = root / "db" / "migration"
            migration_dir.mkdir(parents=True)
            (migration_dir / "V1__init.sql").write_text(
                "CREATE TABLE users (id int primary key);\n",
                encoding="utf-8",
            )

            java_dir = root / "src" / "main" / "java" / "demo"
            java_dir.mkdir(parents=True)
            (java_dir / "UserEntity.java").write_text(
                """
package demo;
import jakarta.persistence.*;

@Entity
@Table(name = "users")
class UserEntity {
  @Id Long id;
  @OneToMany java.util.List<OrderEntity> orders;
}
""".strip(),
                encoding="utf-8",
            )
            (java_dir / "UserRepository.java").write_text(
                """
package demo;
interface UserRepository extends JpaRepository<UserEntity, Long> {}
""".strip(),
                encoding="utf-8",
            )
            (java_dir / "UserService.java").write_text(
                """
package demo;
@Service
class UserService {
  UserEntity findUser(Long id) { return null; }
}
""".strip(),
                encoding="utf-8",
            )
            (java_dir / "UserMapper.java").write_text(
                """
package demo;
@Mapper
interface UserMapper {}
""".strip(),
                encoding="utf-8",
            )
            mapper_dir = resources_dir / "mapper"
            mapper_dir.mkdir()
            (mapper_dir / "UserMapper.xml").write_text(
                """
<mapper namespace="demo.UserMapper">
  <select id="findUser">select * from users</select>
</mapper>
""".strip(),
                encoding="utf-8",
            )

            tests_dir = root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_users_api.py").write_text(
                "def test_users_api(client):\n    id = client.get('/api/users/123')\n",
                encoding="utf-8",
            )
            (tests_dir / "UserCard.test.tsx").write_text(
                "import { UserCard } from '../src/UserCard';\n",
                encoding="utf-8",
            )
            (tests_dir / "test_service.py").write_text(
                "def test_user_service():\n    UserService = object\n",
                encoding="utf-8",
            )
            (tests_dir / "test_unmatched.py").write_text(
                "def test_misc():\n    assert True\n",
                encoding="utf-8",
            )

            facts = scan_project(root)
            claims = build_trace_claims(facts)
            gaps = detect_gaps(facts)
            spec_out = root / "spec"
            write_spec_bundle(facts, claims, gaps, spec_out)

            self.assertIn("/api/users/123", {link.endpoint for link in facts.api_links})
            users_link = next(link for link in facts.api_links if link.endpoint == "/api/users/123")
            self.assertIn(users_link.matched_route, {"/api/users/:id", "/api/users/{id}"})
            self.assertIn(users_link.match_type, {"param", "method-mismatch"})
            self.assertIn(users_link.confidence, {"medium", "low"})
            self.assertTrue(
                {
                    call.matched_route
                    for call in facts.api_calls
                    if call.endpoint == "/api/users/123"
                }
                & {"GET /api/users/:id", "GET /api/users/{id}"}
            )

            express_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "express" and contract.path == "/api/users/:id"
            )
            self.assertIn("path:req.params.id", express_contract.request_hints)
            self.assertIn("query:req.query.expand", express_contract.request_hints)
            self.assertIn("response:res.json", express_contract.response_hints)
            self.assertIn("200", express_contract.status_codes)
            post_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "express" and contract.path == "/api/profile"
            )
            self.assertIn("body:req.body.name", post_contract.request_hints)
            self.assertIn("201", post_contract.status_codes)
            fastapi_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "fastapi" and contract.path == "/api/users/{id}"
            )
            self.assertIn("path:id:str", fastapi_contract.request_hints)
            self.assertIn("query:expand:str | None", fastapi_contract.request_hints)
            self.assertTrue(fastapi_contract.status_codes)
            flask_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "flask" and contract.path == "/api/search/<term>"
            )
            self.assertIn("path:term", flask_contract.request_hints)
            self.assertIn("body:request.json", flask_contract.request_hints)

            data_kinds = {fact.kind for fact in facts.data_layers}
            self.assertIn("prisma-schema", data_kinds)
            self.assertIn("sql-migration", data_kinds)
            self.assertIn("mybatis-mapper", data_kinds)
            self.assertIn("jpa-entity", data_kinds)
            self.assertIn("sqlalchemy", data_kinds)
            self.assertIn("django-model", data_kinds)
            self.assertIn("drizzle", data_kinds)

            runtime_kinds = {fact.kind for fact in facts.runtime_configs}
            self.assertIn("env-example", runtime_kinds)
            self.assertIn("dockerfile", runtime_kinds)
            self.assertIn("docker-compose", runtime_kinds)
            self.assertIn("github-actions", runtime_kinds)
            self.assertIn("spring-config", runtime_kinds)
            self.assertIn("package-scripts", runtime_kinds)
            env_config = next(fact for fact in facts.runtime_configs if fact.kind == "env-example")
            self.assertIn("env-key:DATABASE_URL", env_config.values)

            mapped_targets = {(item.target_kind, item.target) for item in facts.test_maps}
            self.assertIn(("component", "UserCard"), mapped_targets)
            self.assertIn(("service", "UserService"), mapped_targets)
            self.assertIn("unmatched", {item.target_kind for item in facts.test_maps})

            self.assertIn("/api/users/123", (spec_out / "api-links.md").read_text(encoding="utf-8"))
            self.assertIn("req.params.id", (spec_out / "api-contracts.md").read_text(encoding="utf-8"))
            self.assertIn("prisma-schema", (spec_out / "data-layer.md").read_text(encoding="utf-8"))
            self.assertIn("env-key:DATABASE_URL", (spec_out / "runtime-config.md").read_text(encoding="utf-8"))
            self.assertIn("UserCard", (spec_out / "test-map.md").read_text(encoding="utf-8"))
            self.assertTrue(facts.feature_maps)
            self.assertTrue(facts.module_boundaries)
            self.assertTrue(facts.refactor_findings)
            self.assertTrue(facts.contract_gaps)
            self.assertTrue(
                any(
                    "/api/users/123" in call
                    for feature in facts.feature_maps
                    for call in feature.api_calls
                )
            )
            self.assertIn("unknown-error", {gap.gap_type for gap in facts.contract_gaps})
            self.assertIn("frontend", {boundary.kind for boundary in facts.module_boundaries})
            self.assertTrue((spec_out / "feature-map.md").exists())
            self.assertTrue((spec_out / "rebuild-spec.md").exists())
            self.assertTrue((spec_out / "refactor-plan.md").exists())
            self.assertTrue((spec_out / "module-boundaries.md").exists())
            self.assertTrue((spec_out / "contract-gaps.md").exists())
            self.assertTrue((spec_out / "spec-diff.md").exists())
            self.assertIn("/api/users/123", (spec_out / "feature-map.md").read_text(encoding="utf-8"))
            self.assertIn("Rebuild Order", (spec_out / "rebuild-spec.md").read_text(encoding="utf-8"))
            self.assertIn("unknown-error", (spec_out / "contract-gaps.md").read_text(encoding="utf-8"))
            self.assertIn("Frontend Surface", (spec_out / "module-boundaries.md").read_text(encoding="utf-8"))
            self.assertIn("No previous fact bundle", (spec_out / "spec-diff.md").read_text(encoding="utf-8"))

    def test_scan_project_filters_sample_paths_and_scopes_router_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "@angular/core": "^20.0.0",
    "@angular/router": "^20.0.0",
    "react": "^18.0.0",
    "react-router-dom": "^6.0.0"
  }
}
""".strip(),
                encoding="utf-8",
            )
            (root / "src").mkdir()
            (root / "src" / "App.tsx").write_text(
                """
import { Route } from 'react-router-dom';

export function App() {
  return <Route path="/settings" element={<div />} />;
}
""".strip(),
                encoding="utf-8",
            )
            (root / "src" / "angular-routes.ts").write_text(
                """
import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: 'guide/forms', component: FormsPage },
];
""".strip(),
                encoding="utf-8",
            )
            (root / ".github" / "actions" / "deploy").mkdir(parents=True)
            (root / ".github" / "actions" / "deploy" / "main.js").write_text(
                """
const options = { path: './manifest' };
""".strip(),
                encoding="utf-8",
            )
            (root / "compiler" / "fixtures").mkdir(parents=True)
            (root / "compiler" / "fixtures" / "FixtureComponent.tsx").write_text(
                """
export function FixtureComponent() {
  return <div />;
}
""".strip(),
                encoding="utf-8",
            )
            (root / "examples" / "demo" / "app").mkdir(parents=True)
            (root / "examples" / "demo" / "app" / "page.tsx").write_text(
                """
export default function ExamplePage() {
  return <main />;
}
""".strip(),
                encoding="utf-8",
            )
            (root / "scripts").mkdir()
            (root / "scripts" / "eslint-plugin-react-hooks-test-cases.js").write_text(
                """
export function CaseComponent() {
  return <div />;
}
""".strip(),
                encoding="utf-8",
            )
            (root / "packages" / "next-codemod" / "bin" / "__testfixtures__" / "mixed-router" / "app").mkdir(parents=True)
            (root / "packages" / "next-codemod" / "bin" / "__testfixtures__" / "mixed-router" / "app" / "page.tsx").write_text(
                """
export default function TestFixturePage() {
  return <main />;
}
""".strip(),
                encoding="utf-8",
            )
            (root / "src" / "main" / "resources" / "hudson" / "model" / "Thing").mkdir(parents=True)
            (root / "src" / "main" / "resources" / "hudson" / "model" / "Thing" / "help-name.html").write_text(
                "<html><body>Help text</body></html>\n",
                encoding="utf-8",
            )
            (root / "src" / "main" / "resources" / "hudson" / "model" / "Thing" / "help.html").write_text(
                "<html><body>More help text</body></html>\n",
                encoding="utf-8",
            )
            (root / "war" / "src" / "main" / "webapp" / "help" / "LogRecorder").mkdir(parents=True)
            (root / "war" / "src" / "main" / "webapp" / "help" / "LogRecorder" / "logger.html").write_text(
                "<html><body>Webapp help text</body></html>\n",
                encoding="utf-8",
            )
            (root / "src" / "__tests__").mkdir()
            (root / "src" / "__tests__" / "Example.spec.tsx").write_text(
                """
export function Example() {
  return <div />;
}
""".strip(),
                encoding="utf-8",
            )
            (root / "e2e" / "host" / "app").mkdir(parents=True)
            (root / "e2e" / "host" / "app" / "page.tsx").write_text(
                """
export default function E2EHostPage() {
  return <main />;
}
""".strip(),
                encoding="utf-8",
            )
            (root / "e2e" / "host" / "next.config.js").write_text(
                "module.exports = {};\n",
                encoding="utf-8",
            )

            facts = scan_project(root)
            routes = {(route.route, route.framework, route.kind) for route in facts.frontend_routes}
            components = {component.name for component in facts.components}
            page_paths = {page.path for page in facts.pages}
            test_paths = {file.path for file in facts.test_files}
            sample_paths = {file.path for file in facts.files if file.role == "sample"}
            documentation_paths = {file.path for file in facts.files if file.role == "documentation"}
            framework_names = {framework.name for framework in facts.frameworks}

            self.assertIn(("/settings", "react", "react-router-route"), routes)
            self.assertIn(("/guide/forms", "angular", "angular-route"), routes)
            self.assertNotIn(("./manifest", "react", "react-router-route"), routes)
            self.assertNotIn("FixtureComponent", components)
            self.assertNotIn("ExamplePage", components)
            self.assertNotIn("CaseComponent", components)
            self.assertNotIn("TestFixturePage", components)
            self.assertNotIn("Example", components)
            self.assertNotIn("E2EHostPage", components)
            self.assertIn("compiler/fixtures/FixtureComponent.tsx", sample_paths)
            self.assertIn("examples/demo/app/page.tsx", sample_paths)
            self.assertNotIn("compiler/fixtures/FixtureComponent.tsx", test_paths)
            self.assertIn("scripts/eslint-plugin-react-hooks-test-cases.js", test_paths)
            self.assertIn("packages/next-codemod/bin/__testfixtures__/mixed-router/app/page.tsx", test_paths)
            self.assertIn("src/__tests__/Example.spec.tsx", test_paths)
            self.assertIn("e2e/host/app/page.tsx", test_paths)
            self.assertIn("e2e/host/next.config.js", test_paths)
            self.assertNotIn("next", framework_names)
            self.assertIn("src/main/resources/hudson/model/Thing/help-name.html", documentation_paths)
            self.assertIn("src/main/resources/hudson/model/Thing/help.html", documentation_paths)
            self.assertIn("war/src/main/webapp/help/LogRecorder/logger.html", documentation_paths)
            self.assertNotIn("src/main/resources/hudson/model/Thing/help-name.html", page_paths)
            self.assertNotIn("src/main/resources/hudson/model/Thing/help.html", page_paths)
            self.assertNotIn("war/src/main/webapp/help/LogRecorder/logger.html", page_paths)

    def test_scan_project_detects_react_js_components(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "react": "^18.0.0"
  }
}
""".strip(),
                encoding="utf-8",
            )
            components_dir = root / "src" / "components"
            components_dir.mkdir(parents=True)
            (components_dir / "ArticleList.js").write_text(
                """
import React from 'react';

const ArticleList = props => {
  return (
    <div>
      {props.articles.map(article => <span>{article.title}</span>)}
    </div>
  );
};

export default ArticleList;
""".strip(),
                encoding="utf-8",
            )
            (root / "src" / "reducers.js").write_text(
                """
const SessionReducer = (state, action) => {
  return state;
};
""".strip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            self.assertIn("ArticleList", {component.name for component in facts.components})
            self.assertNotIn("SessionReducer", {component.name for component in facts.components})

    def test_scan_project_detects_nested_next_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "next": "^14.0.0",
    "react": "^18.0.0"
  }
}
""".strip(),
                encoding="utf-8",
            )
            root_app_dir = root / "dashboard" / "final-example" / "app"
            root_app_dir.mkdir(parents=True)
            (root_app_dir / "page.tsx").write_text(
                "export default function Page() { return <main />; }\n",
                encoding="utf-8",
            )
            overview_dir = root / "dashboard" / "final-example" / "app" / "dashboard" / "(overview)"
            overview_dir.mkdir(parents=True)
            (overview_dir / "page.tsx").write_text(
                "export default function Page() { return <main />; }\n",
                encoding="utf-8",
            )
            edit_dir = root / "dashboard" / "final-example" / "app" / "dashboard" / "invoices" / "[id]" / "edit"
            edit_dir.mkdir(parents=True)
            (edit_dir / "page.tsx").write_text(
                "export default function Page() { return <main />; }\n",
                encoding="utf-8",
            )
            pages_dir = root / "demo" / "with-pages" / "pages" / "customers"
            pages_dir.mkdir(parents=True)
            (pages_dir / "[id].js").write_text(
                "export default function CustomerPage() { return <main />; }\n",
                encoding="utf-8",
            )
            pages_root = root / "demo" / "with-pages" / "pages"
            (pages_root / "index.js").write_text(
                "export default function HomePage() { return <main />; }\n",
                encoding="utf-8",
            )
            (pages_root / "_app.js").write_text(
                "export default function App({ Component, pageProps }) { return <Component {...pageProps} />; }\n",
                encoding="utf-8",
            )
            internal_pages_dir = root / "packages" / "next" / "src" / "server" / "normalizers" / "built" / "pages"
            internal_pages_dir.mkdir(parents=True)
            (internal_pages_dir / "page-normalizer.ts").write_text(
                "export function normalize() { return '/internal'; }\n",
                encoding="utf-8",
            )
            nested_src_pages_dir = root / "apps" / "web" / "src" / "pages"
            nested_src_pages_dir.mkdir(parents=True)
            (nested_src_pages_dir / "about.tsx").write_text(
                "export default function AboutPage() { return <main />; }\n",
                encoding="utf-8",
            )

            facts = scan_project(root)
            routes = {route.route for route in facts.frontend_routes}

            self.assertIn("/", routes)
            self.assertIn("/about", routes)
            self.assertIn("/dashboard", routes)
            self.assertIn("/dashboard/invoices/:id/edit", routes)
            self.assertIn("/customers/:id", routes)
            self.assertNotIn("/index", routes)
            self.assertNotIn("/_app", routes)
            self.assertNotIn("/page-normalizer", routes)

    def test_scan_project_distinguishes_django_models_and_migrations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog_dir = root / "catalog"
            migration_dir = catalog_dir / "migrations"
            migration_dir.mkdir(parents=True)
            (catalog_dir / "models.py").write_text(
                """
from django.db import models

class Book(models.Model):
    title = models.CharField(max_length=200)
""".strip(),
                encoding="utf-8",
            )
            (catalog_dir / "apps.py").write_text(
                """
from django.apps import AppConfig

class CatalogConfig(AppConfig):
    name = 'catalog'
""".strip(),
                encoding="utf-8",
            )
            (migration_dir / "0001_initial.py").write_text(
                """
from django.db import migrations, models

class Migration(migrations.Migration):
    operations = [
        migrations.CreateModel(
            name='Book',
            fields=[('id', models.AutoField(primary_key=True))],
        ),
    ]
""".strip(),
                encoding="utf-8",
            )
            settings_dir = root / "locallibrary"
            settings_dir.mkdir()
            (settings_dir / "settings.py").write_text(
                """
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
    }
}
""".strip(),
                encoding="utf-8",
            )

            facts = scan_project(root)
            data_layers = {(fact.path, fact.kind, tuple(fact.details)) for fact in facts.data_layers}

            self.assertIn(("catalog/models.py", "django-model", ("model:Book",)), data_layers)
            self.assertTrue(
                any(
                    path == "catalog/migrations/0001_initial.py"
                    and kind == "django-migration"
                    and "operation:CreateModel" in details
                    for path, kind, details in data_layers
                )
            )
            self.assertFalse(
                any(
                    path in {"catalog/apps.py", "locallibrary/settings.py", "catalog/migrations/0001_initial.py"}
                    and kind == "django-model"
                    for path, kind, _details in data_layers
                )
            )


if __name__ == "__main__":
    unittest.main()
