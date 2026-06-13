from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round38GoFiberCalibrationTests(unittest.TestCase):
    def test_fiber_wrapper_routes_method_contracts_and_gorm_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "go.mod").write_text(
                """
module example.com/demo

go 1.23

require (
  github.com/gofiber/fiber/v2 v2.52.9
  gorm.io/gorm v1.30.0
)
""".strip()
                + "\n",
                encoding="utf-8",
            )
            router = root / "router"
            router.mkdir()
            (router / "router.go").write_text(
                """
package router

import "github.com/gofiber/fiber/v2"

func New() *fiber.App {
  return fiber.New()
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            handler = root / "handler"
            handler.mkdir()
            (handler / "routes.go").write_text(
                """
package handler

import "github.com/gofiber/fiber/v2"

type Handler struct{}

func (h *Handler) Register(r fiber.Router) {
  api := r.Group("/api")
  api.Post("/articles", h.CreateArticle)
  api.Get("/articles/:slug", h.GetArticle)
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (handler / "article.go").write_text(
                """
package handler

import (
  "net/http"
  "github.com/gofiber/fiber/v2"
)

// CreateArticle godoc
// @Param article body articleCreateRequest true "Article to create"
// @Success 201 {object} articleResponse
// @Failure 422 {object} errorResponse
func (h *Handler) CreateArticle(c *fiber.Ctx) error {
  req := &articleCreateRequest{}
  if err := req.bind(c); err != nil {
    return c.Status(http.StatusUnprocessableEntity).JSON(errorResponse{})
  }
  return c.Status(http.StatusCreated).JSON(articleResponse{})
}

// GetArticle godoc
// @Param slug path string true "Slug"
// @Success 200 {object} articleResponse
func (h *Handler) GetArticle(c *fiber.Ctx) error {
  slug := c.Params("slug")
  return c.Status(http.StatusOK).JSON(slug)
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            model = root / "model"
            model.mkdir()
            (model / "article.go").write_text(
                """
package model

import "gorm.io/gorm"

type Article struct {
  gorm.Model
  Slug string `gorm:"uniqueIndex;not null" json:"slug"`
  Favorites []User `gorm:"many2many:favorites;"`
}

type User struct {
  ID uint `gorm:"primaryKey"`
  Email string `gorm:"uniqueIndex"`
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "main.go").write_text(
                """
package main

import "example.com/demo/router"

func main() {
  r := router.New()
  r.Get("/swagger/*", nil)
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.framework, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("fiber", "GET", "/swagger/*", "nil"), routes)
            self.assertIn(("fiber", "POST", "/api/articles", "h.CreateArticle"), routes)
            self.assertIn(("fiber", "GET", "/api/articles/:slug", "h.GetArticle"), routes)

            create_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "fiber" and contract.path == "/api/articles" and contract.method == "POST"
            )
            self.assertIn("body:article:articleCreateRequest", create_contract.request_hints)
            self.assertIn("body:req.bind(c)", create_contract.request_hints)
            self.assertIn("response:c.JSON", create_contract.response_hints)
            self.assertIn("swagger-success:201:articleResponse", create_contract.response_hints)
            self.assertIn("201", create_contract.status_codes)
            self.assertIn("422", create_contract.status_codes)

            models = {model.name: model for model in facts.data_models}
            self.assertIn("Article", models)
            self.assertIn("User", models)
            self.assertIn("embed:gorm.Model", models["Article"].fields)
            self.assertIn("Slug:string", models["Article"].fields)
            self.assertIn("Favorites:[]User", models["Article"].fields)
            self.assertIn("relation:Favorites:many2many:favorites", models["Article"].annotations)
            self.assertIn("primary-key:ID", models["User"].annotations)


if __name__ == "__main__":
    unittest.main()
