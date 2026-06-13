from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round27CalibrationTests(unittest.TestCase):

    def test_scan_project_composes_gin_registration_function_group_prefixes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "go.mod").write_text(
                "module demo\n\nrequire github.com/gin-gonic/gin v1.10.0\n",
                encoding="utf-8",
            )
            (root / "hello.go").write_text(
                """
package main

import (
  "github.com/gin-gonic/gin"
  "demo/articles"
  "demo/users"
)

func main() {
  r := gin.New()
  api := r.Group("/api")
  users.UsersRegister(api.Group("/users"))
  articles.ArticlesRegister(api.Group("/articles"))
  AdminRegister(api.Group("/admin"))
  ping := r.Group("/api/ping")
  ping.GET("/", pingHandler)
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            users_dir = root / "users"
            users_dir.mkdir()
            (users_dir / "routers.go").write_text(
                """
package users

import (
  "net/http"
  "github.com/gin-gonic/gin"
)

func UsersRegister(router *gin.RouterGroup) {
  router.POST("", UsersRegistration)
  router.POST("/", UsersRegistration)
  router.POST("/login", UsersLogin)
}

func UsersRegistration(c *gin.Context) {
  var body UserPayload
  if err := c.ShouldBindJSON(&body); err != nil {
    c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
    return
  }
  c.JSON(http.StatusCreated, gin.H{"user": body})
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            articles_dir = root / "articles"
            articles_dir.mkdir()
            (articles_dir / "routers.go").write_text(
                """
package articles

import (
  "net/http"
  "github.com/gin-gonic/gin"
)

func ArticlesRegister(router *gin.RouterGroup) {
  router.GET("/feed", ArticleFeed)
  router.GET("/:slug", ArticleRetrieve)
}

func ArticleFeed(c *gin.Context) {
  limit := c.Query("limit")
  c.JSON(http.StatusOK, gin.H{"articles": []string{}, "limit": limit})
}

func ArticleRetrieve(c *gin.Context) {
  slug := c.Param("slug")
  c.JSON(http.StatusOK, gin.H{"article": slug})
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "admin.go").write_text(
                """
package main

import "github.com/gin-gonic/gin"

func AdminRegister(router *gin.RouterGroup) {
  v1 := router.Group("/v1")
  v1.GET("/stats", AdminStats)
}

func AdminStats(c *gin.Context) {
  c.JSON(200, gin.H{"stats": true})
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.framework, route.method, route.path) for route in facts.api_routes}
            self.assertIn(("gin", "POST", "/api/users"), routes)
            self.assertIn(("gin", "POST", "/api/users/login"), routes)
            self.assertIn(("gin", "GET", "/api/articles/feed"), routes)
            self.assertIn(("gin", "GET", "/api/articles/:slug"), routes)
            self.assertIn(("gin", "GET", "/api/admin/v1/stats"), routes)
            self.assertIn(("gin", "GET", "/api/ping"), routes)
            self.assertNotIn(("gin", "POST", "/api/users/"), routes)
            self.assertNotIn(("gin", "GET", "/feed"), routes)
            self.assertNotIn(("gin", "POST", "/"), routes)

            mounted = [
                route
                for route in facts.api_routes
                if route.path == "/api/articles/feed"
            ]
            self.assertEqual("go-gin-mounted-route", mounted[0].kind)
            self.assertEqual("hello.go", mounted[0].evidence.file)
            self.assertIn("ArticlesRegister", mounted[0].evidence.note or "")

            contracts = {
                (contract.method, contract.path): contract
                for contract in facts.api_contracts
            }
            feed = contracts[("GET", "/api/articles/feed")]
            self.assertIn("query:limit", feed.request_hints)
            self.assertNotIn("path:slug", feed.request_hints)
            self.assertIn("StatusOK", feed.status_codes)
            self.assertIn("response:c.JSON", feed.response_hints)
            self.assertIn("response-key:articles", feed.response_hints)
            create_user = contracts[("POST", "/api/users")]
            self.assertIn("body:body", create_user.request_hints)
            self.assertNotIn("body:loginValidator.Bind(c)", create_user.request_hints)
            self.assertIn("StatusCreated", create_user.status_codes)
            self.assertNotIn("StatusUnauthorized", create_user.status_codes)
            self.assertIn("response-key:user", create_user.response_hints)
            stats = contracts[("GET", "/api/admin/v1/stats")]
            self.assertIn("200", stats.status_codes)


if __name__ == "__main__":
    unittest.main()
