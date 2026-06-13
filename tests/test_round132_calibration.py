from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round132JpaHibernateFrameworkCalibrationTests(unittest.TestCase):
    def test_spring_data_jpa_and_hibernate_signals_are_reported_as_frameworks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            java_dir = root / "src" / "main" / "java" / "org" / "example"
            resources = root / "src" / "main" / "resources"
            java_dir.mkdir(parents=True)
            resources.mkdir(parents=True)
            (root / "pom.xml").write_text(
                """
<project>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-data-jpa</artifactId>
    </dependency>
    <dependency>
      <groupId>org.hibernate.orm</groupId>
      <artifactId>hibernate-core</artifactId>
    </dependency>
  </dependencies>
</project>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (java_dir / "Owner.java").write_text(
                """
package org.example;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;

@Entity
public class Owner {
  @Id
  private Long id;
  private String name;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (java_dir / "OwnerRepository.java").write_text(
                """
package org.example;

import org.springframework.data.jpa.repository.JpaRepository;

public interface OwnerRepository extends JpaRepository<Owner, Long> {
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (resources / "application.properties").write_text(
                """
spring.jpa.hibernate.ddl-auto=none
spring.jpa.properties.hibernate.default_batch_fetch_size=16
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("spring", "backend"), frameworks)
            self.assertIn(("jpa", "data"), frameworks)
            self.assertIn(("hibernate", "data"), frameworks)

            models = {model.name: model for model in facts.data_models}
            self.assertIn("Owner", models)
            self.assertEqual("entity", models["Owner"].kind)
            self.assertIn("OwnerRepository", {repository.name for repository in facts.repositories})
            self.assertIn("jpa-entity", {data_layer.kind for data_layer in facts.data_layers})


if __name__ == "__main__":
    unittest.main()
