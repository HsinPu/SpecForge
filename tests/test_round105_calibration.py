from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round105TrpcNextPrismaCalibrationTests(unittest.TestCase):
    def test_trpc_procedures_client_calls_links_and_tests_are_precise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src" / "server" / "routers").mkdir(parents=True)
            (root / "src" / "pages" / "api" / "trpc").mkdir(parents=True)
            (root / "src" / "pages" / "post").mkdir(parents=True)
            (root / "prisma").mkdir()
            (root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
            (root / "package.json").write_text(
                """
{
  "scripts": {
    "dev": "next dev",
    "start": "next start",
    "test-unit": "vitest"
  },
  "dependencies": {
    "@prisma/client": "^6.0.0",
    "@trpc/client": "canary",
    "@trpc/next": "canary",
    "@trpc/react-query": "canary",
    "@trpc/server": "canary",
    "next": "^15.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "zod": "^4.0.0"
  },
  "devDependencies": {
    "prisma": "^6.0.0",
    "vitest": "^4.0.0"
  }
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "prisma" / "schema.prisma").write_text(
                """
model Post {
  id        String   @id @default(cuid())
  title     String
  text      String
  createdAt DateTime @default(now())
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src" / "server" / "routers" / "_app.ts").write_text(
                """
import { createCallerFactory, publicProcedure, router } from '../trpc';
import { postRouter } from './post';

export const appRouter = router({
  healthcheck: publicProcedure.query(() => 'yay!'),
  post: postRouter,
});

export const createCaller = createCallerFactory(appRouter);
export type AppRouter = typeof appRouter;
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src" / "server" / "routers" / "post.ts").write_text(
                """
import { TRPCError } from '@trpc/server';
import { z } from 'zod';
import { prisma } from '../prisma';
import { publicProcedure, router } from '../trpc';

const defaultPostSelect = {
  id: true,
  title: true,
  text: true,
};

export const postRouter = router({
  list: publicProcedure
    .input(z.object({ cursor: z.string().nullish() }))
    .query(async ({ input }) => {
      const items = await prisma.post.findMany({
        select: defaultPostSelect,
        where: {},
      });
      return { items, nextCursor: input.cursor };
    }),
  byId: publicProcedure
    .input(z.object({ id: z.string() }))
    .query(async ({ input }) => {
      const post = await prisma.post.findUnique({
        where: { id: input.id },
        select: defaultPostSelect,
      });
      if (!post) {
        throw new TRPCError({ code: 'NOT_FOUND' });
      }
      return post;
    }),
  add: publicProcedure
    .input(z.object({ title: z.string(), text: z.string() }))
    .mutation(async ({ input }) => prisma.post.create({ data: input, select: defaultPostSelect })),
});
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src" / "pages" / "api" / "trpc" / "[trpc].ts").write_text(
                """
import * as trpcNext from '@trpc/server/adapters/next';
import { appRouter } from '../../../server/routers/_app';

export default trpcNext.createNextApiHandler({ router: appRouter });
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src" / "pages" / "_app.tsx").write_text(
                "export default function App({ Component, pageProps }) { return <Component {...pageProps} />; }\n",
                encoding="utf-8",
            )
            (root / "src" / "pages" / "index.tsx").write_text(
                """
import { trpc } from '../utils/trpc';

export default function IndexPage() {
  const postsQuery = trpc.post.list.useInfiniteQuery({ limit: 5 });
  const addPost = trpc.post.add.useMutation();
  return <main>{postsQuery.data && addPost.status}</main>;
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src" / "pages" / "post" / "[id].tsx").write_text(
                """
import { trpc } from '../../utils/trpc';

export default function PostPage() {
  const postQuery = trpc.post.byId.useQuery({ id: '1' });
  return <main>{postQuery.data?.title}</main>;
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src" / "server" / "routers" / "post.test.ts").write_text(
                """
import type { inferProcedureInput } from '@trpc/server';
import type { AppRouter } from './_app';
import { createCaller } from './_app';

test('add and get post', async () => {
  const caller = createCaller({});
  const input: inferProcedureInput<AppRouter['post']['add']> = { title: 'hello', text: 'world' };
  const post = await caller.post.add(input);
  await caller.post.byId({ id: post.id });
});
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            entrypoints = {(entry.kind, entry.path, entry.command) for entry in facts.entrypoints}
            self.assertIn(("next-entrypoint", "src/pages/_app.tsx", "pnpm run dev"), entrypoints)

            route_keys = {(route.method, route.path, route.framework, route.kind, route.request_body) for route in facts.api_routes}
            self.assertIn(("QUERY", "/trpc/healthcheck", "trpc", "trpc-procedure", None), route_keys)
            self.assertIn(("QUERY", "/trpc/post.list", "trpc", "trpc-procedure", "input"), route_keys)
            self.assertIn(("QUERY", "/trpc/post.byId", "trpc", "trpc-procedure", "input"), route_keys)
            self.assertIn(("MUTATION", "/trpc/post.add", "trpc", "trpc-procedure", "input"), route_keys)
            self.assertNotIn(("QUERY", "/trpc/post.select", "trpc", "trpc-procedure", None), route_keys)
            self.assertFalse(any(route.path in {"/trpc/post.where", "/trpc/post.https"} for route in facts.api_routes))

            calls = {(call.method, call.endpoint, call.client) for call in facts.api_calls}
            self.assertIn(("QUERY", "/trpc/post.list", "trpc"), calls)
            self.assertIn(("QUERY", "/trpc/post.byId", "trpc"), calls)
            self.assertIn(("MUTATION", "/trpc/post.add", "trpc"), calls)

            links = {(link.method, link.endpoint, link.matched_route, link.match_type, link.confidence) for link in facts.api_links}
            self.assertIn(("QUERY", "/trpc/post.list", "/trpc/post.list", "exact", "high"), links)
            self.assertIn(("QUERY", "/trpc/post.byId", "/trpc/post.byId", "exact", "high"), links)
            self.assertIn(("MUTATION", "/trpc/post.add", "/trpc/post.add", "exact", "high"), links)

            test_targets = {(item.test_path, item.target_kind, item.target, item.confidence) for item in facts.test_maps}
            self.assertIn(("src/server/routers/post.test.ts", "api-route", "QUERY /trpc/post.byId", "high"), test_targets)


if __name__ == "__main__":
    unittest.main()
