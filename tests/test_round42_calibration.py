from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round42WarpCalibrationTests(unittest.TestCase):
    def test_warp_path_filter_routes_and_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Cargo.toml").write_text(
                """
[package]
name = "demo"
version = "0.1.0"
edition = "2021"

[dependencies]
warp = "0.3"
serde = { version = "1", features = ["derive"] }
""".strip()
                + "\n",
                encoding="utf-8",
            )
            src = root / "src"
            src.mkdir()
            (src / "routes.rs").write_text(
                """
use warp::{self, Filter};

mod handlers;

pub fn routes(state: AppState) -> impl Filter<Extract = impl warp::Reply, Error = warp::Rejection> + Clone {
    warp::path!("api" / "items" / String)
        .and(warp::get())
        .and(warp::header::optional("Authorization"))
        .and(warp::query())
        .and(with_state(state.clone()))
        .map_async(handlers::get_item)
        .or(warp::path!("api" / "items")
            .and(warp::post())
            .and(warp::header("Authorization"))
            .and(warp::body::json())
            .and(with_state(state.clone()))
            .map_async(handlers::create_item))
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (src / "handlers.rs").write_text(
                """
pub struct AppState;
pub struct FindItems;
pub struct AuthRequest;
pub struct ErrorResponse;

pub async fn get_item(
    item_id: String,
    token: Option<String>,
    params: FindItems,
    state: AppState,
) -> Result<impl warp::reply::Reply, ErrorResponse> {
    Ok(warp::reply::json(&item_id))
}

pub async fn create_item(
    token: String,
    form: AuthRequest,
    state: AppState,
) -> Result<impl warp::reply::Reply, ErrorResponse> {
    Ok(warp::reply::json(&form))
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("warp", frameworks)

            routes = {(route.framework, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("warp", "GET", "/api/items/{param1}", "handlers::get_item"), routes)
            self.assertIn(("warp", "POST", "/api/items", "handlers::create_item"), routes)

            get_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "warp" and contract.method == "GET" and contract.path == "/api/items/{param1}"
            )
            self.assertIn("path:param1:String", get_contract.request_hints)
            self.assertIn("header:Authorization", get_contract.request_hints)
            self.assertIn("query:query", get_contract.request_hints)
            self.assertIn("path:item_id:String", get_contract.request_hints)
            self.assertIn("query-model:FindItems", get_contract.request_hints)
            self.assertIn("auth:Authorization", get_contract.request_hints)
            self.assertIn("context:AppState", get_contract.request_hints)
            self.assertIn("response:json", get_contract.response_hints)

            post_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "warp" and contract.method == "POST" and contract.path == "/api/items"
            )
            self.assertIn("body:json", post_contract.request_hints)
            self.assertIn("body-model:AuthRequest", post_contract.request_hints)
            self.assertIn("auth:Authorization", post_contract.request_hints)


if __name__ == "__main__":
    unittest.main()
