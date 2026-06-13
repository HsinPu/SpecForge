from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round40ActixCalibrationTests(unittest.TestCase):
    def test_actix_scope_resource_routes_and_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Cargo.toml").write_text(
                """
[package]
name = "demo"
version = "0.1.0"
edition = "2021"

[dependencies]
actix-web = "4"
serde = { version = "1", features = ["derive"] }
""".strip()
                + "\n",
                encoding="utf-8",
            )
            src = root / "src"
            src.mkdir()
            (src / "routes.rs").write_text(
                """
use actix_web::{web, HttpResponse};

mod users;

fn routes(app: &mut web::ServiceConfig) {
    app.service(web::resource("/").to(index))
        .service(web::scope("/api")
            .service(web::resource("users/{id}")
                .route(web::get().to_async(users::get))
                .route(web::put().to_async(users::update))
            )
        );
}

fn index() -> HttpResponse {
    HttpResponse::Ok().finish()
}

#[get("/health")]
async fn health() -> HttpResponse {
    HttpResponse::Ok().finish()
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (src / "users.rs").write_text(
                """
use actix_web::{web::Data, web::Json, web::Path, HttpRequest, HttpResponse};
use futures::Future;

#[derive(serde::Deserialize)]
pub struct UserPath {
    id: String,
}

#[derive(serde::Deserialize)]
pub struct UpdateUser {
    email: String,
}

pub struct AppState;
pub struct Error;

pub fn get(
    state: Data<AppState>,
    (path, req): (Path<UserPath>, HttpRequest),
) -> impl Future<Item = HttpResponse, Error = Error> {
    HttpResponse::Ok().json(path.id)
}

pub fn update(
    state: Data<AppState>,
    (path, form, req): (Path<UserPath>, Json<UpdateUser>, HttpRequest),
) -> impl Future<Item = HttpResponse, Error = Error> {
    HttpResponse::Created().json(form.email)
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("actix-web", frameworks)

            routes = {(route.framework, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("actix-web", "ANY", "/", "index"), routes)
            self.assertIn(("actix-web", "GET", "/api/users/{id}", "users::get"), routes)
            self.assertIn(("actix-web", "PUT", "/api/users/{id}", "users::update"), routes)
            self.assertIn(("actix-web", "GET", "/health", "health"), routes)

            update_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "actix-web" and contract.method == "PUT" and contract.path == "/api/users/{id}"
            )
            self.assertIn("path:id", update_contract.request_hints)
            self.assertIn("path-model:UserPath", update_contract.request_hints)
            self.assertIn("body:Json<UpdateUser>", update_contract.request_hints)
            self.assertIn("context:Data<AppState>", update_contract.request_hints)
            self.assertIn("request:HttpRequest", update_contract.request_hints)
            self.assertIn("response:HttpResponse::Created", update_contract.response_hints)
            self.assertIn("response:json", update_contract.response_hints)
            self.assertIn("201", update_contract.status_codes)


if __name__ == "__main__":
    unittest.main()
