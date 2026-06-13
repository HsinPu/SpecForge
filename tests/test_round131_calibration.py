from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round131ExpressSequelizeCalibrationTests(unittest.TestCase):
    def test_commonjs_express_mounts_and_sequelize_models_migrations_are_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backend = root / "backend"
            routes = backend / "routes"
            article_routes = routes / "articles"
            models = backend / "models"
            migrations = backend / "migrations"
            frontend = root / "frontend" / "src" / "services"
            article_routes.mkdir(parents=True)
            models.mkdir(parents=True)
            migrations.mkdir(parents=True)
            frontend.mkdir(parents=True)
            (backend / "package.json").write_text(
                '{"dependencies":{"express":"^4.17.2","sequelize":"^6.14.1","pg":"^8.7.3"}}\n',
                encoding="utf-8",
            )
            (root / "frontend" / "package.json").write_text(
                '{"dependencies":{"axios":"^1.0.0","react":"^18.0.0"}}\n',
                encoding="utf-8",
            )
            (backend / "index.js").write_text(
                """
const express = require("express");
const articlesRoutes = require("./routes/articles");
const tagsRoutes = require("./routes/tags");

const app = express();
app.use("/api/articles", articlesRoutes);
app.use("/api/tags", tagsRoutes);
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (routes / "articles.js").write_text(
                """
const express = require("express");
const router = express.Router();
const commentsRoutes = require("./articles/comments");

router.get("/", allArticles);
//* Create Article
router.post("/", verifyToken, createArticle);
router.get("/:slug", singleArticle);
router.use("/", commentsRoutes);

module.exports = router;
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (routes / "tags.js").write_text(
                """
const express = require("express");
const router = express.Router();

router.get("/", async (req, res) => res.json({ tags: [] }));

module.exports = router;
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (article_routes / "comments.js").write_text(
                """
const express = require("express");
const router = express.Router();

router.get("/:slug/comments", allComments);

module.exports = router;
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (models / "Article.js").write_text(
                """
const { Model } = require("sequelize");
module.exports = (sequelize, DataTypes) => {
  class Article extends Model {
    static associate({ User, Tag }) {
      this.belongsTo(User, { foreignKey: "userId", as: "author" });
      this.belongsToMany(Tag, { through: "TagList", foreignKey: "articleId" });
    }
  }
  Article.init(
    {
      slug: DataTypes.STRING,
      title: DataTypes.STRING,
      body: DataTypes.TEXT,
    },
    {
      sequelize,
      modelName: "Article",
    },
  );
  return Article;
};
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (migrations / "20220129140808-create-article.js").write_text(
                """
module.exports = {
  async up(queryInterface, Sequelize) {
    await queryInterface.createTable("Articles", {
      id: { type: Sequelize.INTEGER },
      slug: { type: Sequelize.STRING },
      title: { type: Sequelize.STRING },
      body: { type: Sequelize.TEXT },
    });
  },
};
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (frontend / "getTags.js").write_text(
                """
import axios from "axios";
export async function getTags() {
  return axios.get("/api/tags");
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            self.assertIn("sequelize", {framework.name for framework in facts.frameworks})
            routes_by_key = {(route.method, route.path): route for route in facts.api_routes}
            self.assertIn(("GET", "/api/articles"), routes_by_key)
            self.assertIn(("POST", "/api/articles"), routes_by_key)
            self.assertIn(("GET", "/api/articles/:slug"), routes_by_key)
            self.assertIn(("GET", "/api/articles/:slug/comments"), routes_by_key)
            self.assertIn(("GET", "/api/tags"), routes_by_key)

            models_by_name = {model.name: model for model in facts.data_models}
            self.assertIn("Article", models_by_name)
            self.assertEqual("sequelize-model", models_by_name["Article"].kind)
            self.assertIn("slug:STRING", models_by_name["Article"].fields)
            self.assertIn("relation:belongsTo:User", models_by_name["Article"].annotations)
            self.assertIn("through:TagList", models_by_name["Article"].annotations)

            data_layers = {(fact.kind, fact.name): fact for fact in facts.data_layers}
            self.assertIn(("sequelize-migration", "20220129140808-create-article"), data_layers)
            self.assertIn("table:Articles", data_layers[("sequelize-migration", "20220129140808-create-article")].details)
            self.assertIn(
                ("GET", "/api/tags", "/api/tags", "exact"),
                {(link.method, link.endpoint, link.matched_route, link.match_type) for link in facts.api_links},
            )


if __name__ == "__main__":
    unittest.main()
