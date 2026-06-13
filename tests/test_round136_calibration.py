from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round136AndroidRoomFrameworkCalibrationTests(unittest.TestCase):
    def test_android_room_entity_detects_room_without_jpa_false_positive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gradle = root / "gradle"
            model_dir = root / "core" / "database" / "src" / "main" / "kotlin" / "demo" / "database" / "model"
            gradle.mkdir(parents=True)
            model_dir.mkdir(parents=True)
            (gradle / "libs.versions.toml").write_text(
                """
[libraries]
room-runtime = { group = "androidx.room", name = "room-runtime", version = "2.8.3" }

[plugins]
room = { id = "androidx.room", version = "2.8.3" }
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (model_dir / "NewsResourceEntity.kt").write_text(
                """
package demo.database.model

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "news_resources")
data class NewsResourceEntity(
  @PrimaryKey val id: String,
  val title: String,
)
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("room", "data"), frameworks)
            self.assertNotIn(("jpa", "data"), frameworks)

            models = {(model.name, model.kind) for model in facts.data_models}
            self.assertIn(("NewsResourceEntity", "kotlin-room-entity"), models)


if __name__ == "__main__":
    unittest.main()
