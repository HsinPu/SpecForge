from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round80SaleorDashboardCalibrationTests(unittest.TestCase):
    def test_frontend_graphql_dashboard_noise_entrypoints_and_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "vite build",
    "test": "vitest"
  },
  "dependencies": {
    "@apollo/client": "^3.10.0",
    "@vitejs/plugin-react": "^4.0.0",
    "graphql": "^16.0.0",
    "react": "^18.0.0",
    "vite": "^5.0.0"
  },
  "devDependencies": {
    "@storybook/react-vite": "^8.0.0",
    "@playwright/test": "^1.40.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "vite.config.js").write_text(
                "import react from '@vitejs/plugin-react';\nexport default { plugins: [react()] };\n",
                encoding="utf-8",
            )
            src = root / "src"
            src.mkdir()
            (src / "index.html").write_text("<div id=\"root\"></div>\n", encoding="utf-8")
            (src / "index.tsx").write_text(
                """
import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(<App />);
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (src / "App.tsx").write_text(
                """
import { useState } from "react";

export function App() {
  const [open, setOpen] = useState(false);
  return <button onClick={() => setOpen(!open)}>Toggle</button>;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            graphql_dir = src / "graphql"
            graphql_dir.mkdir()
            (graphql_dir / "mutations.ts").write_text(
                """
import { gql } from "@apollo/client";
import { accountErrorFragment } from "./fragments";

export const attributeDelete = gql`
  ${accountErrorFragment}
  mutation AttributeDelete($id: ID) {
    attributeDelete(id: $id) {
      attributeErrors {
        ...AccountErrorFragment
        field
      }
    }
  }
`;
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (graphql_dir / "queries.ts").write_text(
                """
import { gql } from "@apollo/client";

export const gridAttributes = gql`
  query GridAttributes($hasAttributes: Boolean!) {
    selectedAttributes: attributes(first: 25) @include(if: $hasAttributes) {
      edges {
        node {
          id
        }
      }
    }
  }
`;

export const introspection = gql`
  query EventsIntrospection {
    __schema {
      types {
        name
      }
    }
  }
`;

export const userState = gql`
  query UserState {
    me {
      id
    }
    authenticated @client
    authenticating @client
  }
`;
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (graphql_dir / "fragments.ts").write_text(
                """
import { gql } from "@apollo/client";

export const accountErrorFragment = gql`
  fragment AccountErrorFragment on AccountError {
    field
  }
`;

export const webhookDetailsFragment = gql`
  fragment WebhookDetails on Webhook {
    syncEvents {
      eventType
    }
    asyncEvents {
      eventType
    }
    subscriptionQuery
  }
`;
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (graphql_dir / "hooks.generated.ts").write_text(
                """
import { gql } from "@apollo/client";

export const generatedHook = gql`
  mutation GeneratedHook($id: ID) {
    generatedHook(id: $id) {
      ok
    }
  }
`;
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "schema-main.graphql").write_text(
                '''
schema {
  query: Query
  mutation: Mutation
}

type Query {
  attributes(first: Int): AttributeConnection
  me: User
}

type Mutation {
  taxCountryConfigurationUpdate(
    """
    When `{taxClass: id, rate: null}` is passed, it deletes the rate object.
    """
    updateTaxClassRates: [TaxClassRateInput!]!
  ): TaxCountryConfigurationUpdate @doc(category: "Taxes")

  attributeDelete(
    """ID of an attribute to delete."""
    id: ID
  ): AttributeDelete @doc(category: "Attributes")
}
'''.strip()
                + "\n",
                encoding="utf-8",
            )
            storybook = root / ".storybook"
            storybook.mkdir()
            (storybook / "preview.tsx").write_text(
                """
import { useState } from "react";
export function PreviewOnly() {
  const [open] = useState(false);
  fetch("/storybook-only");
  return <div>{open}</div>;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (storybook / "preview-head.html").write_text(
                "<script>fetch('/storybook-head')</script>\n",
                encoding="utf-8",
            )
            components = src / "components"
            components.mkdir()
            (components / "Button.stories.tsx").write_text(
                """
export function ButtonStory() {
  return <button>Story</button>;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            playwright = root / "playwright" / "api"
            playwright.mkdir(parents=True)
            (playwright / "apps.ts").write_text(
                "export async function setup(request) { await request.post('/playwright-only'); }\n",
                encoding="utf-8",
            )
            lint_rules = root / "lint" / "rules"
            lint_rules.mkdir(parents=True)
            (lint_rules / "named-effects.test.mjs").write_text(
                "test('rule', () => fetch('/lint-test-only'));\n",
                encoding="utf-8",
            )
            assets = root / "assets"
            assets.mkdir()
            (assets / "og.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            public = root / "public"
            public.mkdir()
            (public / "favicon.ico").write_bytes(b"\x00\x00\x01\x00")

            facts = scan_project(root)

            roles = {file.path: file.role for file in facts.files}
            self.assertEqual("generated", roles["src/graphql/hooks.generated.ts"])
            self.assertEqual("sample", roles[".storybook/preview.tsx"])
            self.assertEqual("sample", roles[".storybook/preview-head.html"])
            self.assertEqual("sample", roles["src/components/Button.stories.tsx"])
            self.assertEqual("test", roles["playwright/api/apps.ts"])
            self.assertEqual("test", roles["lint/rules/named-effects.test.mjs"])

            entrypoints = {(entry.path, entry.kind, entry.command) for entry in facts.entrypoints}
            self.assertIn(("src/index.tsx", "vite-react-entrypoint", "npm run dev"), entrypoints)

            asset_facts = {(asset.asset_path, asset.asset_kind, asset.usage_kind) for asset in facts.assets}
            self.assertIn(("assets/og.png", "image", "static-asset"), asset_facts)
            self.assertIn(("public/favicon.ico", "image", "static-asset"), asset_facts)

            routes = {(route.method, route.path, route.response_type) for route in facts.api_routes}
            self.assertIn(("MUTATION", "/graphql#Mutation.taxCountryConfigurationUpdate", "TaxCountryConfigurationUpdate"), routes)
            self.assertIn(("MUTATION", "/graphql#Mutation.attributeDelete", "AttributeDelete"), routes)

            calls = {(call.method, call.endpoint, call.path) for call in facts.api_calls}
            self.assertIn(("MUTATION", "/graphql#Mutation.attributeDelete", "src/graphql/mutations.ts"), calls)
            self.assertIn(("QUERY", "/graphql#Query.attributes", "src/graphql/queries.ts"), calls)
            self.assertIn(("QUERY", "/graphql#Query.me", "src/graphql/queries.ts"), calls)
            self.assertNotIn(("MUTATION", "/graphql#Mutation.generatedHook", "src/graphql/hooks.generated.ts"), calls)
            self.assertFalse(any(call.endpoint in {"/graphql#Mutation.accountErrorFragment", "/graphql#Query.include", "/graphql#Query.__schema", "/graphql#Query.authenticated", "/graphql#Query.authenticating", "/graphql#Subscription.subscriptionQuery"} for call in facts.api_calls))
            self.assertFalse(any(call.endpoint in {"/storybook-only", "/storybook-head", "/playwright-only", "/lint-test-only"} for call in facts.api_calls))
            self.assertNotIn("PreviewOnly", {component.name for component in facts.components})
            self.assertNotIn("ButtonStory", {component.name for component in facts.components})

            link = next(link for link in facts.api_links if link.endpoint == "/graphql#Mutation.attributeDelete")
            self.assertEqual("/graphql#Mutation.attributeDelete", link.matched_route)
            self.assertEqual("high", link.confidence)


if __name__ == "__main__":
    unittest.main()
