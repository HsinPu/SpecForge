from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round112SvelteKitRealworldCalibrationTests(unittest.TestCase):
    def test_sveltekit_app_shell_is_entrypoint_not_static_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "type": "module",
  "scripts": {
    "dev": "vite dev",
    "build": "vite build"
  },
  "devDependencies": {
    "@sveltejs/kit": "^2.0.0",
    "svelte": "^5.0.0",
    "vite": "^7.0.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "pnpm-lock.yaml").write_text("lockfileVersion: '10.0'\n", encoding="utf-8")
            (root / "svelte.config.js").write_text("export default { kit: {} };\n", encoding="utf-8")
            src = root / "src"
            routes = src / "routes"
            routes.mkdir(parents=True)
            (src / "app.html").write_text(
                """
<!doctype html>
<html lang="en">
  <head>%sveltekit.head%</head>
  <body><div>%sveltekit.body%</div></body>
</html>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (routes / "+page.svelte").write_text("<h1>Home</h1>\n", encoding="utf-8")

            facts = scan_project(root)

            entrypoints = {(item.kind, item.path, item.command) for item in facts.entrypoints}
            self.assertIn(("sveltekit-entrypoint", "src/routes/+page.svelte", "pnpm run dev"), entrypoints)

            page_paths = {item.path for item in facts.pages}
            route_sources = {item.path for item in facts.frontend_routes}
            self.assertNotIn("src/app.html", page_paths)
            self.assertNotIn("src/app.html", route_sources)
            self.assertIn("src/routes/+page.svelte", route_sources)


if __name__ == "__main__":
    unittest.main()
