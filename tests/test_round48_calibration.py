from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round48FeathersCalibrationTests(unittest.TestCase):
    def test_feathers_services_contracts_and_mongoose_alias_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"@feathersjs/feathers":"^4.0.0","@feathersjs/express":"^4.0.0","feathers-mongoose":"^8.0.0","mongoose":"^5.0.0"}}\n',
                encoding="utf-8",
            )
            articles = root / "src" / "services" / "articles"
            feed = articles / "feed"
            models = root / "src" / "models"
            articles.mkdir(parents=True)
            feed.mkdir(parents=True)
            models.mkdir(parents=True)
            (root / "src" / "app.js").write_text(
                """
const feathers = require('@feathersjs/feathers');
const express = require('@feathersjs/express');
const app = express(feathers());
app.get('paginate');
app.get('/health', (req, res) => res.send('ok'));
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (articles / "articles.service.js").write_text(
                """
const createService = require('feathers-mongoose');
const createModel = require('../../models/articles.model');
const hooks = require('./articles.hooks');

module.exports = function (app) {
  const Model = createModel(app);
  const paginate = app.get('paginate');
  const options = { Model, paginate };

  app.use('/articles/:slug/comments', createService(options));

  const service = app.service('articles/:slug/comments');
  service.hooks(hooks);
};
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (feed / "feed.service.js").write_text(
                """
const createService = require('./feed.class.js');

module.exports = function (app) {
  app.use('/articles/feed', createService({}));
  const service = app.service('articles/feed');
  service.setup(app);
};
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (feed / "feed.class.js").write_text(
                """
const ferrors = require('@feathersjs/errors');

class Service {
  setup(app) {
    this.app = app;
  }

  async find(params) {
    if (!params.user) {
      throw new ferrors.NotAuthenticated();
    }
    return this.getFeed(params);
  }

  async getFeed(params) {
    const limit = params.query.limit;
    return this.app.service('articles').find({ query: { $limit: limit } });
  }
}

module.exports = function (options) {
  return new Service(options);
};
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (models / "articles.model.js").write_text(
                """
const mongoose = require('mongoose');

module.exports = function (app) {
  const Schema = mongoose.Schema;
  const ArticlesSchema = new Schema({
    title: String,
    favoritesCount: { type: Number, default: 0 },
    userId: Schema.Types.ObjectId,
    tagList: [String]
  }, { timestamps: true });
  return mongoose.model('articles', ArticlesSchema);
};
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("feathers", frameworks)
            self.assertIn("feathers-mongoose", frameworks)
            self.assertIn("mongoose", frameworks)

            routes = {(route.framework, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("express", "GET", "/health", None), routes)
            self.assertNotIn(("express", "GET", "paginate", None), routes)
            self.assertIn(("feathers", "GET", "/articles/:slug/comments", "service.find"), routes)
            self.assertIn(("feathers", "GET", "/articles/:slug/comments/{id}", "service.get"), routes)
            self.assertIn(("feathers", "POST", "/articles/:slug/comments", "service.create"), routes)
            self.assertIn(("feathers", "DELETE", "/articles/:slug/comments/{id}", "service.remove"), routes)
            self.assertIn(("feathers", "GET", "/articles/feed", "service.find"), routes)
            self.assertNotIn(("feathers", "POST", "/articles/feed", "service.create"), routes)

            comments_create = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "feathers"
                and contract.method == "POST"
                and contract.path == "/articles/:slug/comments"
            )
            self.assertIn("path:slug", comments_create.request_hints)
            self.assertIn("body:data", comments_create.request_hints)

            feed_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "feathers" and contract.method == "GET" and contract.path == "/articles/feed"
            )
            self.assertIn("query:params.query.limit", feed_contract.request_hints)
            self.assertIn("auth:params.user", feed_contract.request_hints)
            self.assertIn("service-call:articles.find", feed_contract.response_hints)
            self.assertIn("error:ferrors.", feed_contract.error_hints)

            models_by_name = {model.name: model for model in facts.data_models}
            self.assertIn("articles", models_by_name)
            self.assertEqual("mongoose-model", models_by_name["articles"].kind)
            self.assertIn("favoritesCount:Number", models_by_name["articles"].fields)
            self.assertIn("userId:ObjectId", models_by_name["articles"].fields)
            self.assertIn("tagList:Array<String>", models_by_name["articles"].fields)
            self.assertIn("timestamps:true", models_by_name["articles"].annotations)


if __name__ == "__main__":
    unittest.main()
