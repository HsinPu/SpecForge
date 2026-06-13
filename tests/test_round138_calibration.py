from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round138CargoEntrypointCalibrationTests(unittest.TestCase):
    def test_cargo_build_scripts_and_library_helpers_are_not_runtime_entrypoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / "crates" / "core"
            library = root / "crates" / "searcher" / "src" / "searcher"
            app.mkdir(parents=True)
            library.mkdir(parents=True)
            (root / "Cargo.toml").write_text(
                """
[package]
name = "demo"
version = "0.1.0"
build = "build.rs"

[[bin]]
name = "demo"
path = "crates/core/main.rs"
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "build.rs").write_text("fn main() { println!(\"cargo:rerun-if-changed=build.rs\"); }\n", encoding="utf-8")
            (app / "main.rs").write_text("fn main() { println!(\"hello\"); }\n", encoding="utf-8")
            (library / "glue.rs").write_text(
                """
pub(crate) fn main() {
  println!("helper");
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            entrypoints = {(entrypoint.kind, entrypoint.path, entrypoint.command) for entrypoint in facts.entrypoints}
            self.assertIn(("cargo-main", "crates/core/main.rs", "cargo run"), entrypoints)
            self.assertNotIn(("cargo-main", "build.rs", "cargo run"), entrypoints)
            self.assertFalse(any(entrypoint.path.endswith("glue.rs") for entrypoint in facts.entrypoints))


if __name__ == "__main__":
    unittest.main()
