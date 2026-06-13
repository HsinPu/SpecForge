from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round90KtorKotlinCalibrationTests(unittest.TestCase):
    def test_nested_gradle_ktor_routes_contracts_data_and_tests_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "apps" / "ktor-demo"
            project.mkdir(parents=True)
            (project / "gradlew").write_text("#!/bin/sh\n", encoding="utf-8")
            (project / "settings.gradle.kts").write_text('rootProject.name = "ktor-demo"\n', encoding="utf-8")
            (project / "build.gradle.kts").write_text(
                """
plugins {
    kotlin("jvm") version "2.2.0"
    id("io.ktor.plugin") version "3.2.0"
    application
}

dependencies {
    implementation("io.ktor:ktor-server-core-jvm")
    implementation("io.ktor:ktor-server-netty-jvm")
    implementation("org.jetbrains.exposed:exposed-core:0.57.0")
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            resources = project / "src" / "main" / "resources"
            resources.mkdir(parents=True)
            (resources / "application.conf").write_text(
                """
ktor {
  deployment { port = 8080 }
  application { modules = [ demo.ApplicationKt.module ] }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            source_dir = project / "src" / "main" / "kotlin" / "demo"
            source_dir.mkdir(parents=True)
            (source_dir / "Application.kt").write_text(
                """
package demo

import io.ktor.http.HttpStatusCode
import io.ktor.server.application.Application
import io.ktor.server.application.call
import io.ktor.server.engine.embeddedServer
import io.ktor.server.netty.Netty
import io.ktor.server.request.receive
import io.ktor.resources.Resource
import io.ktor.server.response.respond
import io.ktor.server.routing.get
import io.ktor.server.routing.post
import io.ktor.server.routing.route
import io.ktor.server.routing.routing
import io.ktor.server.websocket.webSocket

@Resource("/login")
class Login

data class CreateUserRequest(val name: String)
data class UserResponse(val name: String)

fun main() {
    embeddedServer(Netty, port = 8080, module = Application::module).start(wait = true)
}

fun Application.module() {
    routing {
        route("/api") {
            get("/users/{id}") {
                val expand = call.request.queryParameters["expand"]
                call.respond(UserResponse(expand ?: "demo"))
            }
            post("/users") {
                val input = call.receive<CreateUserRequest>()
                call.respond(HttpStatusCode.Created, UserResponse(input.name))
            }
            webSocket("/ws") {
            }
        }
        get<Login> {
            call.respond("login")
        }
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            dao_dir = source_dir / "dao"
            dao_dir.mkdir()
            (dao_dir / "Users.kt").write_text(
                """
package demo.dao

import org.jetbrains.exposed.sql.SchemaUtils
import org.jetbrains.exposed.sql.Table
import org.jetbrains.exposed.sql.transactions.transaction

object Users : Table("users") {
    val id = integer("id")
    val name = varchar("name", 255)
}

fun createSchema() = transaction {
    SchemaUtils.create(Users)
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            test_dir = project / "src" / "test" / "kotlin" / "demo"
            test_dir.mkdir(parents=True)
            (test_dir / "ApplicationTest.kt").write_text(
                """
package demo

import io.ktor.client.request.get
import io.ktor.server.testing.testApplication
import kotlin.test.Test

class ApplicationTest {
    @Test
    fun userDetailRouteWorks() = testApplication {
        val response = client.get("/api/users/42")
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("ktor", "backend"), frameworks)

            commands = {(command.path, command.name, tuple(command.options)) for command in facts.commands}
            self.assertIn(
                ("apps/ktor-demo/build.gradle.kts", "./gradlew build", ("cwd:apps/ktor-demo",)),
                commands,
            )
            self.assertIn(
                ("apps/ktor-demo/build.gradle.kts", "./gradlew run", ("cwd:apps/ktor-demo",)),
                commands,
            )

            entrypoints = {(entrypoint.kind, entrypoint.path, entrypoint.command) for entrypoint in facts.entrypoints}
            self.assertIn(
                ("ktor-app", "apps/ktor-demo/src/main/resources/application.conf", "./gradlew run"),
                entrypoints,
            )
            runtime_configs = {(config.path, config.kind): config.values for config in facts.runtime_configs}
            ktor_config = runtime_configs[("apps/ktor-demo/src/main/resources/application.conf", "ktor-config")]
            self.assertIn("port:8080", ktor_config)
            self.assertIn("module:demo.ApplicationKt.module", ktor_config)

            routes = {(route.method, route.path, route.framework): route for route in facts.api_routes}
            self.assertIn(("GET", "/api/users/{id}", "ktor"), routes)
            self.assertIn(("POST", "/api/users", "ktor"), routes)
            self.assertIn(("WS", "/api/ws", "ktor"), routes)
            self.assertIn(("GET", "/login", "ktor"), routes)
            get_route = routes[("GET", "/api/users/{id}", "ktor")]
            self.assertIn(("id", "path", True), [(param.name, param.source, param.required) for param in get_route.parameters])
            self.assertIn(("expand", "query", False), [(param.name, param.source, param.required) for param in get_route.parameters])
            post_route = routes[("POST", "/api/users", "ktor")]
            self.assertEqual("CreateUserRequest", post_route.request_body)

            data_layers = {(layer.kind, layer.name): layer.details for layer in facts.data_layers}
            exposed = data_layers[("exposed-data", "Users")]
            self.assertIn("library:exposed", exposed)
            self.assertIn("table:users", exposed)
            self.assertIn("column:name", exposed)

            contracts = {(contract.method, contract.path, contract.framework): contract for contract in facts.api_contracts}
            post_contract = contracts[("POST", "/api/users", "ktor")]
            self.assertIn("body:CreateUserRequest", post_contract.request_hints)
            self.assertIn("Created", post_contract.status_codes)

            test_maps = {test_map.test_path: test_map for test_map in facts.test_maps}
            test_map = test_maps["apps/ktor-demo/src/test/kotlin/demo/ApplicationTest.kt"]
            self.assertEqual("api-route", test_map.target_kind)
            self.assertEqual("GET /api/users/{id}", test_map.target)


if __name__ == "__main__":
    unittest.main()
