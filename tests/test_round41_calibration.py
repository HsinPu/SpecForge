from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round41RocketCalibrationTests(unittest.TestCase):
    def test_rocket_attribute_routes_mount_prefixes_and_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Cargo.toml").write_text(
                """
[package]
name = "demo"
version = "0.1.0"
edition = "2021"

[dependencies]
rocket = { version = "0.5", features = ["json"] }
serde = { version = "1", features = ["derive"] }
""".strip()
                + "\n",
                encoding="utf-8",
            )
            src = root / "src"
            routes = src / "routes"
            routes.mkdir(parents=True)
            (src / "lib.rs").write_text(
                """
#[macro_use]
extern crate rocket;

mod routes;

pub fn rocket() -> _ {
    rocket::build().mount(
        "/api",
        routes![
            routes::users::post_users,
            routes::users::get_user,
            routes::articles::get_articles,
        ],
    )
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (routes / "mod.rs").write_text("pub mod articles;\npub mod users;\n", encoding="utf-8")
            (routes / "users.rs").write_text(
                """
use rocket::serde::json::{Json, Value};
use rocket::State;

pub struct AppState;
pub struct Auth;
pub struct Db;
pub struct Errors;

#[derive(serde::Deserialize)]
pub struct NewUser {
    email: String,
}

#[post("/users", format = "json", data = "<new_user>")]
pub async fn post_users(new_user: Json<NewUser>, db: Db, state: &State<AppState>) -> Result<Value, Errors> {
    json!({ "ok": true })
}

#[get("/user")]
pub async fn get_user(auth: Auth, db: Db, state: &State<AppState>) -> Option<Value> {
    json!({ "ok": true })
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (routes / "articles.rs").write_text(
                """
use rocket::serde::json::Value;

pub struct Auth;
pub struct Db;
pub struct FindArticles;

#[get("/articles/<slug>?<params..>")]
pub async fn get_articles(slug: String, params: FindArticles, auth: Option<Auth>, db: Db) -> Value {
    json!({ "slug": slug })
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("rocket", frameworks)

            routes_seen = {(route.framework, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("rocket", "POST", "/api/users", "routes::users::post_users"), routes_seen)
            self.assertIn(("rocket", "GET", "/api/user", "routes::users::get_user"), routes_seen)
            self.assertIn(("rocket", "GET", "/api/articles/<slug>", "routes::articles::get_articles"), routes_seen)

            post_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "rocket" and contract.method == "POST" and contract.path == "/api/users"
            )
            self.assertIn("body:new_user", post_contract.request_hints)
            self.assertIn("body:Json<NewUser>", post_contract.request_hints)
            self.assertIn("context:State<AppState>", post_contract.request_hints)
            self.assertIn("context:Db", post_contract.request_hints)
            self.assertIn("response:json", post_contract.response_hints)
            self.assertIn("response:result", post_contract.response_hints)

            article_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "rocket" and contract.method == "GET" and contract.path == "/api/articles/<slug>"
            )
            self.assertIn("path:slug", article_contract.request_hints)
            self.assertIn("query:params", article_contract.request_hints)
            self.assertIn("path:slug:String", article_contract.request_hints)
            self.assertIn("query-model:FindArticles", article_contract.request_hints)
            self.assertIn("auth:Auth", article_contract.request_hints)


if __name__ == "__main__":
    unittest.main()
