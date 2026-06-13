from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.renderers.backend import render_backend
from specforge.renderers.overview import render_architecture
from specforge.scanner import scan_project


class Round106RedwoodCalibrationTests(unittest.TestCase):
    def test_redwood_entrypoints_commands_routes_services_and_prisma_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "web" / "src").mkdir(parents=True)
            (root / "api" / "src" / "functions").mkdir(parents=True)
            (root / "api" / "src" / "graphql").mkdir(parents=True)
            (root / "api" / "src" / "services" / "posts").mkdir(parents=True)
            (root / "api" / "db").mkdir(parents=True)
            (root / "scripts").mkdir()
            (root / "yarn.lock").write_text("# yarn lock\n", encoding="utf-8")
            (root / "package.json").write_text(
                """
{
  "private": true,
  "workspaces": { "packages": ["api", "web"] },
  "devDependencies": { "@redwoodjs/core": "^0.38.0" },
  "prisma": { "seed": "yarn rw exec seed" }
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "redwood.toml").write_text(
                """
[web]
  port = 8910
  apiUrl = "/.redwood/functions"
[api]
  port = 8911
""".lstrip(),
                encoding="utf-8",
            )
            (root / "scripts" / "seed.js").write_text("export default async () => {}\n", encoding="utf-8")
            (root / "web" / "src" / "App.js").write_text(
                """
import { RedwoodProvider } from '@redwoodjs/web';
import Routes from './Routes';

export default function App() {
  return <RedwoodProvider><Routes /></RedwoodProvider>;
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "web" / "src" / "Routes.js").write_text(
                """
import { Router, Route, Set } from '@redwoodjs/router';

const Routes = () => (
  <Router>
    <Route path="/admin/{id}/edit" page={EditPostPage} name="editPost" />
    <Route path="/" page={HomePage} name="home" />
    <Route notfound page={NotFoundPage} />
  </Router>
);

export default Routes;
""".lstrip(),
                encoding="utf-8",
            )
            (root / "api" / "src" / "functions" / "graphql.js").write_text(
                """
import { createGraphQLHandler } from '@redwoodjs/graphql-server';
import services from 'src/services/**/*.{js,ts}';
import sdls from 'src/graphql/**/*.sdl.{js,ts}';

export const handler = createGraphQLHandler({ services, sdls });
""".lstrip(),
                encoding="utf-8",
            )
            (root / "api" / "src" / "graphql" / "posts.sdl.js").write_text(
                """
export const schema = gql`
  type Post {
    id: Int!
    title: String!
  }

  type Query {
    allPosts: [Post!]!
    findPostById(id: Int!): Post
  }

  type Mutation {
    createPost(input: CreatePostInput!): Post!
  }
`;
""".lstrip(),
                encoding="utf-8",
            )
            (root / "api" / "src" / "services" / "posts" / "posts.js").write_text(
                """
import { db } from 'src/lib/db';

const validate = (input) => input;

export const allPosts = () => db.post.findMany();
export const findPostById = ({ id }) => db.post.findUnique({ where: { id } });
export const createPost = ({ input }) => {
  validate(input);
  return db.post.create({ data: input });
};
""".lstrip(),
                encoding="utf-8",
            )
            (root / "api" / "db" / "schema.prisma").write_text(
                """
model Post {
  id    Int    @id @default(autoincrement())
  title String
}
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            entrypoints = {(entry.kind, entry.path, entry.command) for entry in facts.entrypoints}
            self.assertIn(("redwood-web-app", "web/src/App.js", "yarn redwood dev"), entrypoints)
            self.assertIn(("redwood-graphql-function", "api/src/functions/graphql.js", "yarn redwood dev"), entrypoints)

            commands = {command.name for command in facts.commands}
            self.assertIn("yarn redwood dev", commands)
            self.assertIn("yarn redwood test", commands)
            self.assertIn("yarn redwood prisma migrate dev", commands)
            self.assertIn("yarn redwood prisma db seed", commands)

            frontend_routes = {(route.framework, route.kind, route.route) for route in facts.frontend_routes}
            self.assertIn(("redwood", "redwood-route", "/admin/{id}/edit"), frontend_routes)
            self.assertIn(("redwood", "redwood-route", "/"), frontend_routes)
            self.assertIn(("redwood", "redwood-notfound-route", "*"), frontend_routes)

            api_routes = {(route.framework, route.method, route.path) for route in facts.api_routes}
            self.assertIn(("graphql", "QUERY", "/graphql#Query.allPosts"), api_routes)
            self.assertIn(("graphql", "MUTATION", "/graphql#Mutation.createPost"), api_routes)

            services = {(service.name, service.path, tuple(service.methods)) for service in facts.services}
            self.assertIn(("posts", "api/src/services/posts/posts.js", ("allPosts", "findPostById", "createPost")), services)

            models = {(model.kind, model.name, model.path) for model in facts.data_models}
            self.assertIn(("prisma-model", "Post", "api/db/schema.prisma"), models)

            self.assertIn("Service symbols: 1", render_backend(facts))
            self.assertIn("redwood: 0 route(s), 1 service symbol(s)", render_architecture(facts))


if __name__ == "__main__":
    unittest.main()
