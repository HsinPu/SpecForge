from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round110RustAxumCalibrationTests(unittest.TestCase):
    def test_cargo_main_entrypoint_commands_and_axum_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Cargo.toml").write_text(
                """
[package]
name = "axum-demo"
version = "0.1.0"
edition = "2021"

[dependencies]
axum = "0.7"
tokio = { version = "1", features = ["macros", "rt-multi-thread"] }
serde = { version = "1", features = ["derive"] }
""".strip()
                + "\n",
                encoding="utf-8",
            )
            src = root / "src"
            src.mkdir()
            (src / "main.rs").write_text(
                """
use axum::{routing::get, Router};

#[tokio::main]
async fn main() {
    let app = Router::new().route("/health", get(health));
    let _ = app;
}

async fn health() -> &'static str {
    "ok"
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            entrypoints = {(entry.kind, entry.path, entry.command) for entry in facts.entrypoints}
            self.assertIn(("cargo-main", "src/main.rs", "cargo run"), entrypoints)

            commands = {command.name for command in facts.commands}
            self.assertIn("cargo run", commands)
            self.assertIn("cargo build", commands)
            self.assertIn("cargo test", commands)

            routes = {(route.framework, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("axum", "GET", "/health", "health"), routes)


if __name__ == "__main__":
    unittest.main()
