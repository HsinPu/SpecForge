from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round7CalibrationTests(unittest.TestCase):

    def test_scan_project_detects_angular_httpclient_nuxt_fetch_and_gorm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "@angular/core": "^20.0.0",
    "@angular/common": "^20.0.0",
    "nuxt": "^3.0.0",
    "vue": "^3.0.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            angular = root / "src" / "app" / "features" / "article" / "services"
            angular.mkdir(parents=True)
            (angular / "articles.service.ts").write_text(
                """
import { HttpClient } from '@angular/common/http';

export class ArticlesService {
  constructor(private readonly http: HttpClient) {}

  list() {
    return this.http.get<{ articles: Article[] }>('/articles');
  }

  favorite(slug: string) {
    return this.http.post<{ article: Article }>(`/articles/${slug}/favorite`, {});
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            nuxt_page = root / "pages"
            nuxt_page.mkdir()
            (nuxt_page / "index.vue").write_text(
                """
<script setup lang="ts">
const { data } = await useFetch('/api/articles', { method: 'POST' })
</script>
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "go.mod").write_text(
                """
module demo

require (
  github.com/gin-gonic/gin v1.10.0
  gorm.io/gorm v1.25.12
  gorm.io/driver/sqlite v1.5.7
)
""".strip()
                + "\n",
                encoding="utf-8",
            )
            go_src = root / "users"
            go_src.mkdir()
            (go_src / "models.go").write_text(
                """
package users

import "gorm.io/gorm"

type UserModel struct {
  gorm.Model
  Username string `gorm:"column:username"`
  Email string `gorm:"column:email;uniqueIndex"`
}

func Migrate(db *gorm.DB) {
  db.AutoMigrate(&UserModel{})
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (go_src / "database.go").write_text(
                """
package users

import (
  "gorm.io/driver/sqlite"
  "gorm.io/gorm"
)

func Init(path string) *gorm.DB {
  db, _ := gorm.Open(sqlite.Open(path), &gorm.Config{})
  return db
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (go_src / "unit_test.go").write_text(
                """
package users

import "gorm.io/gorm"

func TestMigrate(db *gorm.DB) {
  db.AutoMigrate(&TestOnlyModel{})
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            files = {file.path: file for file in facts.files}
            self.assertEqual("service", files["src/app/features/article/services/articles.service.ts"].role)

            api_calls = {(call.client, call.method, call.endpoint) for call in facts.api_calls}
            self.assertIn(("angular-httpclient", "GET", "/articles"), api_calls)
            self.assertIn(("angular-httpclient", "POST", "/articles/:slug/favorite"), api_calls)
            self.assertIn(("useFetch", "POST", "/api/articles"), api_calls)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("gorm", frameworks)

            data_layers = {(item.kind, item.name) for item in facts.data_layers}
            self.assertIn(("gorm-model", "UserModel"), data_layers)
            self.assertIn(("gorm-migration", "models"), data_layers)
            self.assertIn(("gorm-database", "database"), data_layers)
            self.assertNotIn(("gorm-migration", "unit_test"), data_layers)
            self.assertIn("test", {file.role for file in facts.files if file.path.endswith("unit_test.go")})


if __name__ == "__main__":
    unittest.main()
