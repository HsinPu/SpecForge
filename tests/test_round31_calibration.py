from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.renderers.backend import render_spring
from specforge.scanner import scan_project


class Round31SpringOpenApiCalibrationTests(unittest.TestCase):
    def test_spring_openapi_operation_routes_match_controller_methods(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pom.xml").write_text(
                """
<project>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
  </dependencies>
</project>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            resources = root / "src" / "main" / "resources"
            resources.mkdir(parents=True)
            (resources / "openapi.yml").write_text(
                """
openapi: 3.0.1
paths:
  /users:
    get:
      operationId: listUsers
      parameters:
        - name: q
          in: query
      responses:
        200:
          description: ok
    post:
      operationId: createUser
      requestBody:
        content:
          application/json:
            schema:
              type: object
      responses:
        201:
          description: created
  /missing:
    get:
      operationId: missingHandler
      responses:
        200:
          description: ok
""".strip()
                + "\n",
                encoding="utf-8",
            )
            controller = root / "src" / "main" / "java" / "demo"
            controller.mkdir(parents=True)
            (controller / "UserController.java").write_text(
                """
package demo;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("api")
public class UserController {
    public ResponseEntity<List<UserDto>> listUsers(String q) {
        return null;
    }

    public ResponseEntity<UserDto> createUser(UserDto userDto) {
        return null;
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.framework, route.kind, route.method, route.path, route.handler, route.response_type) for route in facts.api_routes}
            self.assertIn(("openapi", "openapi-spec-route", "GET", "/users", "listUsers", "responses:200"), routes)
            self.assertIn(("spring", "spring-openapi-operation-route", "GET", "/api/users", "listUsers", "ResponseEntity<List<UserDto>>"), routes)
            self.assertIn(("spring", "spring-openapi-operation-route", "POST", "/api/users", "createUser", "ResponseEntity<UserDto>"), routes)
            self.assertNotIn(("spring", "spring-openapi-operation-route", "GET", "/api/missing", "missingHandler", None), routes)
            self.assertIn("handler:", render_spring(facts))

    def test_java_model_extraction_ignores_comment_text_and_doc_annotations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "src" / "main" / "java" / "demo"
            model.mkdir(parents=True)
            (model / "BaseEntity.java").write_text(
                """
package demo;

/**
 * Base class for all entities.
 *
 * @author example
 */
@MappedSuperclass
public class BaseEntity {
    @Id
    private Integer id;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            models = {model.name: model for model in facts.data_models}
            self.assertIn("BaseEntity", models)
            self.assertNotIn("for", models)
            self.assertNotIn("author", models["BaseEntity"].annotations)
            self.assertIn("MappedSuperclass", models["BaseEntity"].annotations)


if __name__ == "__main__":
    unittest.main()
