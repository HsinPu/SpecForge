from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round6CalibrationTests(unittest.TestCase):

    def test_scan_project_detects_desktop_cms_clojure_and_mybatis_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            (root / "package.json").write_text(
                """
{
  "main": "src/main.ts",
  "dependencies": {
    "@tauri-apps/api": "^2.0.0",
    "electron": "^31.0.0",
    "react": "^19.0.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "src-tauri").mkdir()
            (root / "src-tauri" / "tauri.conf.json").write_text('{"identifier":"com.example.demo"}\n', encoding="utf-8")
            (root / "src-tauri" / "Cargo.toml").write_text(
                """
[package]
name = "demo-tauri"
version = "0.1.0"

[dependencies]
tauri = "2"
""".strip()
                + "\n",
                encoding="utf-8",
            )
            src = root / "src"
            src.mkdir()
            (src / "main.ts").write_text(
                """
import { app, BrowserWindow } from 'electron';
import { invoke } from '@tauri-apps/api/core';
""".strip()
                + "\n",
                encoding="utf-8",
            )

            wp = root / "wp-content" / "plugins" / "demo"
            wp.mkdir(parents=True)
            (wp / "demo.php").write_text(
                """
<?php
/*
Plugin Name: Demo Exporter
*/
add_action('init', 'demo_init');
register_rest_route('demo/v1', '/export', array('methods' => 'GET', 'callback' => 'demo_export'));
""".strip()
                + "\n",
                encoding="utf-8",
            )

            drupal = root / "modules" / "demo"
            drupal.mkdir(parents=True)
            (drupal / "demo.routing.yml").write_text(
                """
demo.example:
  path: '/demo/example'
  defaults:
    _controller: '\\Drupal\\demo\\Controller\\DemoController::index'
  requirements:
    _permission: 'access content'
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "project.clj").write_text(
                """
(defproject demo "0.1.0"
  :dependencies [[ring/ring-core "1.12.0"]
                 [metosin/reitit "0.7.0"]
                 [luminus/ring-ttl-session "0.3.3"]])
""".strip()
                + "\n",
                encoding="utf-8",
            )
            clj = root / "src" / "demo"
            clj.mkdir(parents=True, exist_ok=True)
            (clj / "routes.clj").write_text(
                """
(ns demo.routes
  (:require [compojure.core :refer [GET POST defroutes]]
            [reitit.ring :as ring]))

(defroutes app-routes
  (GET "/login" [] "login")
  (POST "/users" [] "create"))

(def app
  (ring/ring-handler
    (ring/router
      [["/api/users" {:get list-users :post create-user}]])))
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "pom.xml").write_text(
                """
<project>
  <dependencies>
    <dependency>
      <groupId>org.mybatis.spring.boot</groupId>
      <artifactId>mybatis-spring-boot-starter</artifactId>
    </dependency>
  </dependencies>
</project>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            mapper = root / "src" / "main" / "resources" / "mapper"
            mapper.mkdir(parents=True)
            (mapper / "UserMapper.xml").write_text(
                """
<mapper namespace="demo.UserMapper">
  <select id="findAll">select * from users</select>
</mapper>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            groovy_mapper = root / "src" / "main" / "groovy" / "demo"
            groovy_mapper.mkdir(parents=True)
            (groovy_mapper / "AccountMapper.groovy").write_text(
                """
package demo

import org.apache.ibatis.annotations.Mapper

@Mapper
interface AccountMapper {
  Account findByUsername(String username)
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertTrue(
                {
                    "clojure-ring",
                    "drupal",
                    "electron",
                    "mybatis",
                    "reitit",
                    "tauri",
                    "wordpress",
                }
                <= frameworks
            )
            api_routes = {(route.framework, route.method, route.path) for route in facts.api_routes}
            self.assertIn(("wordpress", "GET", "/wp-json/demo/v1/export"), api_routes)
            self.assertIn(("drupal", "ANY", "/demo/example"), api_routes)
            self.assertIn(("clojure-ring", "GET", "/login"), api_routes)
            self.assertIn(("clojure-ring", "POST", "/users"), api_routes)
            self.assertIn(("reitit", "GET", "/api/users"), api_routes)
            self.assertIn(("reitit", "POST", "/api/users"), api_routes)
            mybatis_mappers = [item for item in facts.data_layers if item.kind == "mybatis-mapper"]
            self.assertGreaterEqual(len(mybatis_mappers), 2)
            self.assertIn("AccountMapper", {item.name for item in mybatis_mappers})
            self.assertIn("tauri", {dependency.name for dependency in facts.dependencies})
            self.assertIn("ring/ring-core", {dependency.name for dependency in facts.dependencies})


if __name__ == "__main__":
    unittest.main()
