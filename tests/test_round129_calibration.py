from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round129SpringPetclinicCalibrationTests(unittest.TestCase):
    def test_spring_comments_do_not_create_routes_and_thymeleaf_forms_are_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            java_dir = root / "src" / "main" / "java" / "org" / "example"
            templates = root / "src" / "main" / "resources" / "templates" / "owners"
            fragments = root / "src" / "main" / "resources" / "templates" / "fragments"
            java_dir.mkdir(parents=True)
            templates.mkdir(parents=True)
            fragments.mkdir(parents=True)
            (root / "pom.xml").write_text(
                """
<project>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
      <groupId>org.thymeleaf</groupId>
      <artifactId>thymeleaf-spring6</artifactId>
    </dependency>
  </dependencies>
</project>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (java_dir / "OwnerController.java").write_text(
                """
package org.example;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;

@Controller
public class OwnerController {
  /**
   * Called before each and every @RequestMapping annotated method.
   * @return Owner object always has an id
   */
  @ModelAttribute("owner")
  public Owner loadOwner() {
    return new Owner();
  }

  @GetMapping("/owners")
  public String owners() {
    return "owners/findOwners";
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (templates / "findOwners.html").write_text(
                """
<!doctype html>
<html xmlns:th="http://www.thymeleaf.org">
  <body>
    <form th:object="${owner}" th:action="@{/owners}" method="get">
      <input class="form-control" th:field="*{lastName}" />
    </form>
  </body>
</html>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (fragments / "inputField.html").write_text(
                """
<html xmlns:th="http://www.thymeleaf.org">
  <body>
    <form></form>
  </body>
</html>
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("GET", "/owners", "owners"), routes)
            self.assertFalse(any(route.method == "ANY" and route.path == "/" for route in facts.api_routes))

            forms = {(form.method, form.action, tuple(form.fields), form.source) for form in facts.forms}
            self.assertIn(
                ("GET", "/owners", ("lastName",), "src/main/resources/templates/owners/findOwners.html"),
                forms,
            )
            self.assertFalse(any(form.source.endswith("fragments/inputField.html") for form in facts.forms))


if __name__ == "__main__":
    unittest.main()
