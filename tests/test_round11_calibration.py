from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round11CalibrationTests(unittest.TestCase):

    def test_scan_project_detects_non_rest_contract_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "@trpc/server": "^10.0.0",
    "@trpc/react-query": "^10.0.0",
    "graphql": "^16.0.0",
    "socket.io": "^4.0.0",
    "react": "^19.0.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            routers = root / "src" / "server" / "routers"
            routers.mkdir(parents=True)
            (routers / "post.routes.ts").write_text(
                """
import { protectedProcedure, publicProcedure, router } from '../trpc';

export const postRouter = router({
  list: publicProcedure.query(({ ctx }) => ctx.posts.list()),
  create: protectedProcedure.input(PostInput).mutation(({ input, ctx }) => ctx.posts.create(input)),
});
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (routers / "auth.routes.ts").write_text(
                """
import { protectedProcedure, router } from '../trpc';

export const authRouter = router({
  loginUser: protectedProcedure.mutation(({ input, ctx }) => ctx.auth.login(input)),
});
""".strip()
                + "\n",
                encoding="utf-8",
            )
            pages = root / "src" / "pages"
            pages.mkdir(parents=True)
            (pages / "posts.tsx").write_text(
                """
import { api } from '../utils/api';

export function PostsPage() {
  const posts = api.post.list.useQuery();
  const createPost = api.post.create.useMutation();
  const login = api.loginUser.useMutation();
  return <main>{posts.data?.length ?? 0}</main>;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (pages / "articleQueries.ts").write_text(
                """
import { gql } from '@apollo/client';

export const ArticleListQuery = gql`
  query ArticleListQuery {
    article(slug: "hello") {
      title
    }
  }
`;

export const CreateArticleMutation = gql`
  mutation CreateArticleMutation($input: ArticleInput!) {
    createArticle(input: $input) {
      title
    }
  }
`;
""".strip()
                + "\n",
                encoding="utf-8",
            )

            schema = root / "schema.graphql"
            schema.write_text(
                """
type Query {
  article(slug: String!): Article
}

type Mutation {
  createArticle(input: ArticleInput!): Article
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            js_schema = root / "server" / "schema" / "root-query.type.js"
            js_schema.parent.mkdir(parents=True, exist_ok=True)
            js_schema.write_text(
                """
const RootQuery = `
  type RootQuery {
    items: [Item]
  }
`;

const RootMutation = `
  type RootMutation {
    addItem(name: String!): Item
  }
`;
""".strip()
                + "\n",
                encoding="utf-8",
            )

            proto = root / "proto" / "route_guide.proto"
            proto.parent.mkdir()
            proto.write_text(
                """
syntax = "proto3";
package demo.routeguide;

service RouteGuide {
  rpc GetFeature(Point) returns (Feature) {}
  rpc ListFeatures(Rectangle) returns (stream Feature) {}
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            server = root / "server"
            server.mkdir(exist_ok=True)
            (server / "socket.js").write_text(
                """
const socketio = require('socket.io');
const io = socketio(server);

io.on('connect', (socket) => {
  socket.on('join', ({ room }) => {});
  socket.on('sendMessage', (message) => {});
});
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (pages / "chat.tsx").write_text(
                """
export function Chat({ socket }) {
  socket.emit('join', { room: 'general' });
  socket.emit('sendMessage', 'hello');
  return <main>chat</main>;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("trpc", frameworks)
            self.assertIn("graphql", frameworks)
            self.assertIn("grpc", frameworks)
            self.assertIn("socketio", frameworks)

            api_routes = {(route.framework, route.method, route.path) for route in facts.api_routes}
            self.assertIn(("trpc", "QUERY", "/trpc/post.list"), api_routes)
            self.assertIn(("trpc", "MUTATION", "/trpc/post.create"), api_routes)
            self.assertIn(("trpc", "MUTATION", "/trpc/auth.loginUser"), api_routes)
            self.assertIn(("graphql", "QUERY", "/graphql#Query.article"), api_routes)
            self.assertIn(("graphql", "MUTATION", "/graphql#Mutation.createArticle"), api_routes)
            self.assertIn(("graphql", "QUERY", "/graphql#Query.items"), api_routes)
            self.assertIn(("graphql", "MUTATION", "/graphql#Mutation.addItem"), api_routes)
            self.assertIn(("grpc", "RPC", "/demo.routeguide.RouteGuide/GetFeature"), api_routes)
            self.assertIn(("grpc", "RPC", "/demo.routeguide.RouteGuide/ListFeatures"), api_routes)
            self.assertIn(("socketio", "EVENT", "socket.io#join"), api_routes)
            self.assertIn(("socketio", "EVENT", "socket.io#sendMessage"), api_routes)

            api_calls = {(call.client, call.method, call.endpoint) for call in facts.api_calls}
            self.assertIn(("trpc", "QUERY", "/trpc/post.list"), api_calls)
            self.assertIn(("trpc", "MUTATION", "/trpc/post.create"), api_calls)
            self.assertIn(("trpc", "MUTATION", "/trpc/loginUser"), api_calls)
            self.assertIn(("graphql", "QUERY", "/graphql#Query.article"), api_calls)
            self.assertIn(("graphql", "MUTATION", "/graphql#Mutation.createArticle"), api_calls)
            self.assertNotIn(("graphql", "MUTATION", "/graphql#Mutation.input"), api_calls)
            self.assertIn(("socket.io", "EVENT", "socket.io#join"), api_calls)
            self.assertIn(("socket.io", "EVENT", "socket.io#sendMessage"), api_calls)

            api_links = {(link.method, link.endpoint, link.matched_route, link.match_type, link.confidence) for link in facts.api_links}
            self.assertIn(("MUTATION", "/trpc/loginUser", "/trpc/auth.loginUser", "trpc-procedure", "medium"), api_links)
            self.assertIn(("QUERY", "/graphql#Query.article", "/graphql#Query.article", "exact", "high"), api_links)
            self.assertIn(("MUTATION", "/graphql#Mutation.createArticle", "/graphql#Mutation.createArticle", "exact", "high"), api_links)


if __name__ == "__main__":
    unittest.main()
