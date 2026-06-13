from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round148RustHyperCalibrationTests(unittest.TestCase):
    def test_rust_hyper_match_routes_are_detected_with_handler_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Cargo.toml").write_text(
                """
[package]
name = "hyper-demo"
version = "0.1.0"
edition = "2021"

[dependencies]
hyper = "1"
serde = { version = "1", features = ["derive"] }
""".strip()
                + "\n",
                encoding="utf-8",
            )
            src = root / "src"
            src.mkdir()
            (src / "server.rs").write_text(
                """
use hyper::{Method, Request, Response, StatusCode};

async fn handle_request_inner(req: Request<()>) -> Result<Response<()>, Error> {
    match (req.method(), req.uri().path()) {
        (&Method::GET, "/health") => {
            Ok(health_check().await?)
        }
        (&Method::POST, "/api/register") => {
            if locked {
                return Err(AppError::Status(StatusCode::NOT_FOUND));
            }
            Ok(
                handlers::register(req.into_body())
                    .await?
                    .into_response(),
            )
        }
        // (&Method::DELETE, "/commented") => { handlers::delete().await? }
        _ => {
            let mut res = Response::new(());
            *res.status_mut() = StatusCode::NOT_FOUND;
            Ok(res)
        }
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.framework, route.kind, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("hyper", "hyper-match-route", "GET", "/health", "server::health_check"), routes)
            self.assertIn(("hyper", "hyper-match-route", "POST", "/api/register", "handlers::register"), routes)
            self.assertNotIn(("hyper", "hyper-match-route", "DELETE", "/commented", "handlers::delete"), routes)

            register = next(route for route in facts.api_routes if route.path == "/api/register")
            self.assertEqual("body", register.request_body)
            self.assertEqual("Response", register.response_type)


if __name__ == "__main__":
    unittest.main()
