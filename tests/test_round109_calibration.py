from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round109GoGinCalibrationTests(unittest.TestCase):
    def test_go_main_file_entrypoint_commands_and_gin_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "go.mod").write_text(
                """
module example.com/ginapp

go 1.21

require (
  github.com/gin-gonic/gin v1.10.0
  gorm.io/gorm v1.25.12
)
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "hello.go").write_text(
                """
package main

import "github.com/gin-gonic/gin"

func main() {
  r := gin.Default()
  api := r.Group("/api")
  api.GET("/ping", Ping)
  r.Run(":8080")
}

func Ping(c *gin.Context) {
  c.JSON(200, gin.H{"message": "pong"})
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            entrypoints = {(entry.kind, entry.path, entry.command) for entry in facts.entrypoints}
            self.assertIn(("go-main", "hello.go", "go run ."), entrypoints)

            commands = {command.name for command in facts.commands}
            self.assertIn("go run .", commands)
            self.assertIn("go build ./...", commands)
            self.assertIn("go test ./...", commands)

            routes = {(route.framework, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("gin", "GET", "/api/ping", "Ping"), routes)


if __name__ == "__main__":
    unittest.main()
