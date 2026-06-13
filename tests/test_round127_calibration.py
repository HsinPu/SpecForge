from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round127ExpressMountedRouterCalibrationTests(unittest.TestCase):

    def test_express_router_mount_prefix_middleware_and_inline_contract_hints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            routes = root / "src" / "app" / "routes"
            article = routes / "article"
            article.mkdir(parents=True)
            (root / "package.json").write_text(
                '{"dependencies":{"express":"^5.0.0","@prisma/client":"^6.0.0"}}\n',
                encoding="utf-8",
            )
            (routes / "routes.ts").write_text(
                """
import { Router } from 'express';
import articlesController from './article/article.controller';

const api = Router()
  .use(articlesController);

export default Router().use('/api', api);
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (article / "article.controller.ts").write_text(
                """
import { Router } from 'express';
import auth from '../auth/auth';

const router = Router();

router.get('/articles/:slug', auth.optional, async (req, res, next) => {
  const article = await getArticle(req.params.slug, req.query.preview);
  res.json({ article });
});

router.post('/articles', auth.required, async (req, res, next) => {
  const article = await createArticle(req.body.article);
  res.status(201).json({ article });
});

export default router;
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes_by_key = {(route.method, route.path): route for route in facts.api_routes}
            get_route = routes_by_key[("GET", "/api/articles/:slug")]
            self.assertEqual("inline", get_route.handler)
            self.assertEqual("express-mounted-route", get_route.kind)
            self.assertEqual([("slug", "path")], [(param.name, param.source) for param in get_route.parameters])
            self.assertNotIn(("GET", "/articles/:slug"), routes_by_key)

            contracts = {(contract.method, contract.path): contract for contract in facts.api_contracts}
            get_contract = contracts[("GET", "/api/articles/:slug")]
            self.assertIn("path:req.params.slug", get_contract.request_hints)
            self.assertIn("query:req.query.preview", get_contract.request_hints)
            post_contract = contracts[("POST", "/api/articles")]
            self.assertIn("body:req.body.article", post_contract.request_hints)
            self.assertIn("201", post_contract.status_codes)


if __name__ == "__main__":
    unittest.main()
