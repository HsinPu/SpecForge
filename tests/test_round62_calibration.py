from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round62RedwoodCalibrationTests(unittest.TestCase):
    def test_redwood_routes_graphql_prisma_and_fixture_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "web" / "src" / "components" / "PostCell").mkdir(parents=True)
            (root / "api" / "src" / "graphql").mkdir(parents=True)
            (root / "api" / "src" / "services" / "posts").mkdir(parents=True)
            (root / "api" / "db").mkdir(parents=True)
            (root / "__fixtures__" / "fake-app" / "web" / "src").mkdir(parents=True)
            (root / "__fixtures__" / "fake-app" / "api" / "db").mkdir(parents=True)
            (root / "__fixtures__" / "fake-app").joinpath("package.json").write_text(
                """
{
  "dependencies": {
    "react-native": "^0.75.0"
  }
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "@redwoodjs/api": "^8.0.0",
    "@redwoodjs/graphql-server": "^8.0.0",
    "@redwoodjs/router": "^8.0.0",
    "@redwoodjs/web": "^8.0.0",
    "@prisma/client": "^5.0.0",
    "react": "^18.0.0"
  }
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "redwood.toml").write_text(
                """
[web]
  title = "SpecForge Redwood"
[api]
  port = 8911
""".lstrip(),
                encoding="utf-8",
            )
            (root / "web" / "src" / "Routes.tsx").write_text(
                """
import { Router, Route, Set } from '@redwoodjs/router';

const Routes = () => (
  <Router>
    <Route path="/" page={HomePage} name="home" />
    <Route path="/posts/{id:Int}" page={PostPage} name="post" />
    <Set wrap={PrivateLayout}>
      <Route path="/admin" page={AdminPage} name="admin" />
    </Set>
    <Route notfound page={NotFoundPage} />
  </Router>
);

export default Routes;
""".lstrip(),
                encoding="utf-8",
            )
            (root / "web" / "src" / "components" / "PostCell" / "PostCell.tsx").write_text(
                """
import { gql } from '@redwoodjs/web';

export const QUERY = gql`
  query FindPost($id: Int!) {
    post(id: $id) {
      id
      title
    }
  }
`;

export const Loading = () => <div>Loading...</div>;
export const Success = ({ post }) => <article>{post.title}</article>;
""".lstrip(),
                encoding="utf-8",
            )
            (root / "web" / "src" / "RouteExamples.ts").write_text(
                """
import '@redwoodjs/router';

// <Route path="/comment-example" page={CommentPage} name="comment" />
const routeTemplate = '<Route path="/string-example" page={StringPage} name="string" />';
""".lstrip(),
                encoding="utf-8",
            )
            (root / "web" / "src" / "RouteGenerator.ts").write_text(
                """
const generatedRoutes = [
  `<Route path="/generator-string" page={GeneratedPage} name="generated" />`,
];
""".lstrip(),
                encoding="utf-8",
            )
            (root / "api" / "src" / "graphql" / "posts.sdl.ts").write_text(
                """
export const schema = gql`
  type Post {
    id: Int!
    title: String!
  }

  type Query {
    post(id: Int!): Post!
    posts: [Post!]!
  }
`;
""".lstrip(),
                encoding="utf-8",
            )
            (root / "api" / "src" / "services" / "posts" / "posts.ts").write_text(
                """
import { db } from 'src/lib/db';

export const post = ({ id }) => db.post.findUnique({ where: { id } });
export const posts = () => db.post.findMany();
""".lstrip(),
                encoding="utf-8",
            )
            (root / "api" / "db" / "schema.prisma").write_text(
                """
datasource db {
  provider = "sqlite"
  url      = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-js"
}

model Post {
  id    Int    @id @default(autoincrement())
  title String
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "__fixtures__" / "fake-app" / "web" / "src" / "Routes.tsx").write_text(
                """
import { Router, Route } from '@redwoodjs/router';

export default () => (
  <Router>
    <Route path="/fixture-only" page={FixturePage} name="fixture" />
  </Router>
);
""".lstrip(),
                encoding="utf-8",
            )
            (root / "__fixtures__" / "fake-app" / "api" / "db" / "schema.prisma").write_text(
                """
model FixtureOnly {
  id Int @id
}
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("redwood", "frontend"), frameworks)
            self.assertIn(("redwood", "backend"), frameworks)
            self.assertIn(("prisma", "data"), frameworks)
            self.assertNotIn(("react-native", "mobile"), frameworks)

            frontend_routes = {(route.route, route.framework, route.kind) for route in facts.frontend_routes}
            self.assertIn(("/", "redwood", "redwood-route"), frontend_routes)
            self.assertIn(("/posts/{id:Int}", "redwood", "redwood-route"), frontend_routes)
            self.assertIn(("/admin", "redwood", "redwood-route"), frontend_routes)
            self.assertIn(("*", "redwood", "redwood-notfound-route"), frontend_routes)
            self.assertNotIn(("/fixture-only", "redwood", "redwood-route"), frontend_routes)
            self.assertNotIn(("/comment-example", "redwood", "redwood-route"), frontend_routes)
            self.assertNotIn(("/string-example", "redwood", "redwood-route"), frontend_routes)
            self.assertFalse(any(route.route == "/generator-string" for route in facts.frontend_routes))
            self.assertFalse(any(route.kind == "react-router-route" for route in facts.frontend_routes))

            api_routes = {(route.method, route.path, route.framework, route.kind) for route in facts.api_routes}
            self.assertIn(("QUERY", "/graphql#Query.post", "graphql", "graphql-schema-field"), api_routes)
            self.assertIn(("QUERY", "/graphql#Query.posts", "graphql", "graphql-schema-field"), api_routes)

            api_calls = {(call.method, call.endpoint, call.client) for call in facts.api_calls}
            self.assertIn(("QUERY", "/graphql#Query.post", "graphql"), api_calls)
            self.assertTrue(any(link.endpoint == "/graphql#Query.post" and link.matched_route == "/graphql#Query.post" for link in facts.api_links))

            models = {(model.name, model.kind) for model in facts.data_models}
            self.assertIn(("Post", "prisma-model"), models)
            self.assertNotIn(("FixtureOnly", "prisma-model"), models)

            components = {(component.name, component.framework) for component in facts.components}
            self.assertIn(("Success", "redwood"), components)


if __name__ == "__main__":
    unittest.main()
