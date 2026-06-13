from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round119GraphqlCalibrationTests(unittest.TestCase):

    def test_nestjs_code_first_graphql_resolvers_are_api_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"@nestjs/graphql":"^12.0.0","graphql":"^16.0.0"}}\n',
                encoding="utf-8",
            )
            src = root / "src" / "article"
            src.mkdir(parents=True)
            (src / "article.resolver.ts").write_text(
                """
import { Args, Int, Mutation, Query, Resolver } from '@nestjs/graphql';

class Article {}
class ArticleCreateInput {}
class ArticleWhereInput {}
class FindManyArticleArgs {}

@Resolver(() => Article)
export class ArticleResolver {
  @Query(() => [Article])
  async articles(@Args() args: FindManyArticleArgs) {
    return [];
  }

  @Query(() => Int)
  async countArticles(
    @Args({ name: 'where', nullable: true, type: () => ArticleWhereInput })
    where: ArticleWhereInput,
  ) {
    return 0;
  }

  @Mutation(() => Article)
  async createArticle(@Args('input') input: ArticleCreateInput) {
    return input;
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.framework, route.method, route.path, route.handler, route.response_type) for route in facts.api_routes}
            self.assertIn(("graphql", "QUERY", "/graphql#Query.articles", "articles", "[Article]"), routes)
            self.assertIn(("graphql", "QUERY", "/graphql#Query.countArticles", "countArticles", "Int"), routes)
            self.assertIn(("graphql", "MUTATION", "/graphql#Mutation.createArticle", "createArticle", "Article"), routes)

            articles = next(route for route in facts.api_routes if route.path == "/graphql#Query.articles")
            self.assertEqual([("args", "argument", "FindManyArticleArgs")], [(param.name, param.source, param.type) for param in articles.parameters])
            count = next(route for route in facts.api_routes if route.path == "/graphql#Query.countArticles")
            self.assertEqual([("where", "argument", "ArticleWhereInput", False)], [(param.name, param.source, param.type, param.required) for param in count.parameters])
            create = next(route for route in facts.api_routes if route.path == "/graphql#Mutation.createArticle")
            self.assertEqual([("input", "argument", "ArticleCreateInput")], [(param.name, param.source, param.type) for param in create.parameters])


if __name__ == "__main__":
    unittest.main()
