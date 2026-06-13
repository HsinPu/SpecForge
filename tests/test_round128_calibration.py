from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round128SpringGraphqlJavaDataCalibrationTests(unittest.TestCase):
    def test_spring_static_imported_request_method_graphqls_and_java_data_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            java_dir = root / "src" / "main" / "java" / "io" / "spring" / "api"
            data_dir = root / "src" / "main" / "java" / "io" / "spring" / "application" / "data"
            schema_dir = root / "src" / "main" / "resources" / "schema"
            java_dir.mkdir(parents=True)
            data_dir.mkdir(parents=True)
            schema_dir.mkdir(parents=True)
            (root / "pom.xml").write_text(
                """
<project>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
      <groupId>com.graphql-java</groupId>
      <artifactId>graphql-java</artifactId>
    </dependency>
  </dependencies>
</project>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (java_dir / "UsersApi.java").write_text(
                """
package io.spring.api;

import static org.springframework.web.bind.annotation.RequestMethod.POST;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class UsersApi {
  private UserService userService;

  @RequestMapping(path = "/users", method = POST)
  public UserData createUser(@RequestBody RegisterParam registerParam) {
    return userService.createUser(registerParam);
  }
}

class RegisterParam {
  private String email;
  private String password;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (data_dir / "ArticleData.java").write_text(
                """
package io.spring.application.data;

import java.util.List;
import lombok.Data;

@Data
public class ArticleData {
  private String id;
  private String title;
  private List<String> tagList;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (schema_dir / "schema.graphqls").write_text(
                """
schema {
  query: Query
  mutation: Mutation
}

type Query {
  article(slug: String!): Article
}

type Mutation {
  createArticle(input: CreateArticleInput!): ArticlePayload
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.framework, route.method, route.path): route for route in facts.api_routes}
            self.assertIn(("spring", "POST", "/users"), routes)
            self.assertNotIn(("spring", "ANY", "/users"), routes)
            self.assertIn(("graphql", "QUERY", "/graphql#Query.article"), routes)
            self.assertIn(("graphql", "MUTATION", "/graphql#Mutation.createArticle"), routes)
            self.assertIn("graphql", {framework.name for framework in facts.frameworks})

            models = {model.name: model for model in facts.data_models}
            self.assertIn("ArticleData", models)
            self.assertIn("RegisterParam", models)
            self.assertEqual(["String id", "String title", "List<String> tagList"], models["ArticleData"].fields)
            self.assertEqual(["String email", "String password"], models["RegisterParam"].fields)


if __name__ == "__main__":
    unittest.main()
