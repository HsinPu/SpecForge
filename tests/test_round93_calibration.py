from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round93NestjsCalibrationTests(unittest.TestCase):
    def test_nestjs_route_path_params_are_preserved_without_method_params(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "scripts": {
    "start": "nest start",
    "test": "jest"
  },
  "dependencies": {
    "@nestjs/common": "^10.0.0",
    "@nestjs/core": "^10.0.0",
    "@nestjs/typeorm": "^10.0.0",
    "typeorm": "^0.3.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            src = root / "src"
            src.mkdir()
            (src / "articles.controller.ts").write_text(
                """
import { Body, Controller, Delete, Get, Param, Post } from '@nestjs/common';
import { CreateArticleDto } from './create-article.dto';

@Controller('articles')
export class ArticlesController {
  @Get(':slug')
  findOne(@Param('slug') slug: string) {
    return { slug };
  }

  @Delete(':slug/comments/:id')
  deleteComment() {
    return { deleted: true };
  }

  @Post(':slug/favorite')
  favorite() {
    return { favorited: true };
  }

  @Post()
  create(@Body('article') article: CreateArticleDto) {
    return article;
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (src / "create-article.dto.ts").write_text(
                """
export class CreateArticleDto {
  title: string;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "ormconfig.json.example").write_text(
                """
{
  "type": "mysql",
  "host": "localhost",
  "port": 3306,
  "username": "user",
  "password": "secret",
  "database": "demo",
  "entities": ["src/**/**.entity{.ts,.js}"],
  "synchronize": true
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "nestconfig.json").write_text(
                '{"language":"ts","entryFile":"src/main.ts"}\n',
                encoding="utf-8",
            )
            (root / "nodemon.json").write_text(
                '{"watch":["src"],"ext":"ts","ignore":["src/**/*.spec.ts"],"exec":"node ./index"}\n',
                encoding="utf-8",
            )
            (root / "jest.json").write_text(
                '{"testRegex":"/src/.*\\\\.(test|spec).(ts|tsx|js)$","coverageReporters":["json","lcov"]}\n',
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {
                (route.method, route.path): route
                for route in facts.api_routes
                if route.framework == "nestjs"
            }
            self.assertIn(("GET", "/articles/:slug"), routes)
            self.assertIn(("DELETE", "/articles/:slug/comments/:id"), routes)
            self.assertIn(("POST", "/articles/:slug/favorite"), routes)
            self.assertIn(("POST", "/articles"), routes)

            find_one_params = {
                (param.source, param.name, param.type)
                for param in routes[("GET", "/articles/:slug")].parameters
            }
            self.assertIn(("path", "slug", "string"), find_one_params)
            self.assertEqual(
                1,
                sum(1 for param in routes[("GET", "/articles/:slug")].parameters if param.name == "slug"),
            )

            delete_params = {
                (param.source, param.name, param.type)
                for param in routes[("DELETE", "/articles/:slug/comments/:id")].parameters
            }
            self.assertIn(("path", "slug", None), delete_params)
            self.assertIn(("path", "id", None), delete_params)
            self.assertTrue(
                all(param.evidence.file == "src/articles.controller.ts" for param in routes[("DELETE", "/articles/:slug/comments/:id")].parameters)
            )

            favorite_params = {
                (param.source, param.name, param.type)
                for param in routes[("POST", "/articles/:slug/favorite")].parameters
            }
            self.assertIn(("path", "slug", None), favorite_params)
            self.assertEqual("CreateArticleDto", routes[("POST", "/articles")].request_body)

            contracts = {
                (contract.method, contract.path): contract
                for contract in facts.api_contracts
                if contract.framework == "nestjs"
            }
            self.assertIn("path:slug", contracts[("DELETE", "/articles/:slug/comments/:id")].request_hints)
            self.assertIn("path:id", contracts[("DELETE", "/articles/:slug/comments/:id")].request_hints)
            self.assertIn("body:CreateArticleDto", contracts[("POST", "/articles")].request_hints)

            runtime = {(fact.path, fact.kind): fact for fact in facts.runtime_configs}
            self.assertIn(("ormconfig.json.example", "typeorm-config-template"), runtime)
            self.assertIn("config-key:password", runtime[("ormconfig.json.example", "typeorm-config-template")].values)
            self.assertIn("port:3306", runtime[("ormconfig.json.example", "typeorm-config-template")].values)
            self.assertIn("entity-glob:src/**/**.entity{.ts,.js}", runtime[("ormconfig.json.example", "typeorm-config-template")].values)
            self.assertNotIn("secret", " ".join(runtime[("ormconfig.json.example", "typeorm-config-template")].values))
            self.assertIn(("nestconfig.json", "nestjs-config"), runtime)
            self.assertIn("entrypoint:src/main.ts", runtime[("nestconfig.json", "nestjs-config")].values)
            self.assertIn(("nodemon.json", "nodemon-config"), runtime)
            self.assertIn("command:node ./index", runtime[("nodemon.json", "nodemon-config")].values)
            self.assertIn(("jest.json", "jest-config"), runtime)
            self.assertIn("coverage-reporter:lcov", runtime[("jest.json", "jest-config")].values)


if __name__ == "__main__":
    unittest.main()
