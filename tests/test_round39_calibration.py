from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round39AxumCalibrationTests(unittest.TestCase):
    def test_axum_contract_hints_and_rust_data_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Cargo.toml").write_text(
                """
[package]
name = "demo"
version = "0.1.0"
edition = "2021"

[dependencies]
axum = "0.7"
serde = { version = "1", features = ["derive"] }
sqlx = "0.7"
""".strip()
                + "\n",
                encoding="utf-8",
            )
            src = root / "src"
            src.mkdir()
            (src / "routes.rs").write_text(
                """
use axum::extract::{Path, Query, Extension};
use axum::routing::{delete, get, post};
use axum::{Json, Router};

mod listing;

pub fn router() -> Router {
    Router::new()
        .route("/api/articles", get(list_articles).post(create_article))
        .route("/api/articles/feed", get(listing::feed_articles))
        .route("/api/articles/:slug", get(get_article))
        .route("/api/articles/:slug/comments/:comment_id", delete(delete_comment))
}

#[derive(serde::Deserialize)]
struct ListQuery {
    limit: i64,
    offset: i64,
}

#[derive(serde::Deserialize)]
struct NewArticle {
    title: String,
}

#[derive(serde::Serialize, serde::Deserialize)]
struct ArticleBody<T> {
    article: T,
}

#[derive(serde::Serialize)]
struct Article {
    slug: String,
    title: String,
}

#[derive(serde::Serialize)]
struct Errors {
    errors: HashMap<Cow<'static, str>, Vec<Cow<'static, str>>>,
}

#[derive(sqlx::Type)]
pub struct Timestamptz(pub String);

async fn list_articles(
    Query(query): Query<ListQuery>,
) -> Result<Json<ArticleBody<Article>>, Error> {
    Ok(Json(ArticleBody { article: Article { slug: query.limit.to_string(), title: query.offset.to_string() } }))
}

async fn create_article(
    Extension(ctx): Extension<ApiContext>,
    req: Json<ArticleBody<NewArticle>>,
) -> Result<Json<ArticleBody<Article>>, Error> {
    Ok(Json(ArticleBody { article: Article { slug: req.article.title.clone(), title: req.article.title } }))
}

async fn get_article(
    Path(slug): Path<String>,
) -> Result<Json<ArticleBody<Article>>, Error> {
    Ok(Json(ArticleBody { article: Article { slug, title: String::new() } }))
}

async fn delete_comment(
    Path((slug, comment_id)): Path<(String, i64)>,
) -> Result<()> {
    Ok(())
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (src / "listing.rs").write_text(
                """
pub(in crate) async fn feed_articles(
    query: Query<ListQuery>,
) -> Result<Json<ArticleBody<Article>>, Error> {
    Ok(Json(ArticleBody { article: Article { slug: String::new(), title: query.limit.to_string() } }))
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.framework, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("axum", "GET", "/api/articles", "list_articles"), routes)
            self.assertIn(("axum", "POST", "/api/articles", "create_article"), routes)
            self.assertIn(("axum", "GET", "/api/articles/feed", "listing::feed_articles"), routes)
            self.assertIn(("axum", "GET", "/api/articles/:slug", "get_article"), routes)
            self.assertIn(("axum", "DELETE", "/api/articles/:slug/comments/:comment_id", "delete_comment"), routes)

            create_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "axum" and contract.method == "POST" and contract.path == "/api/articles"
            )
            self.assertIn("body:Json<ArticleBody<NewArticle>>", create_contract.request_hints)
            self.assertIn("context:Extension<ApiContext>", create_contract.request_hints)
            self.assertIn("response:Json<ArticleBody<Article>>", create_contract.response_hints)
            self.assertIn("response:Ok(Json)", create_contract.response_hints)

            get_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "axum" and contract.method == "GET" and contract.path == "/api/articles/:slug"
            )
            self.assertIn("path:slug:String", get_contract.request_hints)

            list_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "axum" and contract.method == "GET" and contract.path == "/api/articles"
            )
            self.assertIn("query:ListQuery", list_contract.request_hints)

            feed_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "axum" and contract.method == "GET" and contract.path == "/api/articles/feed"
            )
            self.assertIn("query:ListQuery", feed_contract.request_hints)
            self.assertIn("response:Json<ArticleBody<Article>>", feed_contract.response_hints)

            delete_contract = next(
                contract
                for contract in facts.api_contracts
                if (
                    contract.framework == "axum"
                    and contract.method == "DELETE"
                    and contract.path == "/api/articles/:slug/comments/:comment_id"
                )
            )
            self.assertIn("path:slug:String", delete_contract.request_hints)
            self.assertIn("path:comment_id:i64", delete_contract.request_hints)

            models = {model.name: model for model in facts.data_models}
            self.assertIn("ArticleBody", models)
            self.assertIn("Article", models)
            self.assertIn("Errors", models)
            self.assertIn("Timestamptz", models)
            self.assertEqual("rust-sqlx-type", models["Timestamptz"].kind)
            self.assertIn("article:T", models["ArticleBody"].fields)
            self.assertIn("slug:String", models["Article"].fields)
            self.assertIn("errors:HashMap<Cow<'static, str>, Vec<Cow<'static, str>>>", models["Errors"].fields)


if __name__ == "__main__":
    unittest.main()
