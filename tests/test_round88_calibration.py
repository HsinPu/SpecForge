from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round88ClojureCalibrationTests(unittest.TestCase):
    def test_clojure_compojure_next_jdbc_project_skeleton_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "deps.edn").write_text(
                """
{:paths ["resources" "src"]
 :deps {org.clojure/clojure {:mvn/version "1.12.4"}
        compojure/compojure {:mvn/version "1.7.2"}
        ring/ring {:mvn/version "1.15.3"}
        selmer/selmer {:mvn/version "1.13.0"}
        com.github.seancorfield/next.jdbc {:mvn/version "1.3.1093"}
        com.stuartsierra/component {:mvn/version "1.2.0"}}
 :aliases {:test {:extra-paths ["test"]}
           :build {:ns-default build}}}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "build.clj").write_text("(ns build)\n", encoding="utf-8")

            src = root / "src" / "demo"
            model = src / "model"
            controller = src / "controllers"
            model.mkdir(parents=True)
            controller.mkdir(parents=True)
            (src / "main.clj").write_text(
                """
(ns demo.main
  (:require [com.stuartsierra.component :as component]
            [compojure.coercions :refer [as-int]]
            [compojure.core :refer [GET POST let-routes]]
            [ring.adapter.jetty :refer [run-jetty]]
            [demo.controllers.user :as user-ctl]
            [demo.model.user-manager :as model])
  (:gen-class))

(defrecord Application [config   ; runtime config
                        database ; dependency
                        state])  ; lifecycle state

(defn my-handler [application]
  (let-routes [wrap identity]
    (GET "/" [] (wrap #'user-ctl/index))
    (GET "/users/:id{[0-9]+}" [id :<< as-int] (wrap #'user-ctl/show))
    (POST "/users/save" [] (wrap #'user-ctl/save))))

(defn -main [& [port]]
  (run-jetty (my-handler nil) {:port (or port 8080)}))

(comment
  (require '[next.jdbc :as jdbc])
  (jdbc/execute! nil ["select * from ghost"]))
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (controller / "user.clj").write_text(
                """
(ns demo.controllers.user
  (:require [selmer.parser :as tmpl]
            [demo.model.user-manager :as model]))

(defn index [req] (tmpl/render-file "views/users/list.html" {}))
(defn show [req] (model/get-user-by-id (:db req) (get-in req [:params :id])))
(defn save [req] (model/save-user (:db req) (:params req)))
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (model / "user_manager.clj").write_text(
                """
(ns demo.model.user-manager
  (:require [next.jdbc :as jdbc]
            [next.jdbc.sql :as sql]))

(def ^:private my-db {:dbtype "sqlite" :dbname "demo_db"})

(defrecord Database [db-spec datasource])

(defn populate [db]
  (jdbc/execute-one! (db) ["create table users (id integer, email varchar(64))"]))

(defn get-user-by-id [db id]
  (sql/get-by-id (db) :users id))

(defn get-users [db]
  (sql/query (db) ["select * from users order by email"]))

(defn save-user [db user]
  (sql/insert! (db) :users user))
""".strip()
                + "\n",
                encoding="utf-8",
            )

            test_dir = root / "test" / "demo" / "model"
            test_dir.mkdir(parents=True)
            (test_dir / "user_manager_test.clj").write_text(
                """
(ns demo.model.user-manager-test
  (:require [clojure.test :refer [deftest is]]
            [demo.model.user-manager :as model]))

(deftest user-test
  (is (model/get-users nil)))
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            commands = {command.name for command in facts.commands}
            self.assertIn("clojure -M", commands)
            self.assertIn("clojure -M:test", commands)
            self.assertIn("clojure -T:build", commands)
            self.assertIn("clojure -M -m demo.main", commands)

            entrypoints = {(entrypoint.kind, entrypoint.path, entrypoint.command) for entrypoint in facts.entrypoints}
            self.assertIn(("clojure-main", "src/demo/main.clj", "clojure -M -m demo.main"), entrypoints)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("clojure-ring", "backend"), frameworks)
            self.assertIn(("compojure", "backend"), frameworks)
            self.assertIn(("selmer", "frontend"), frameworks)
            self.assertIn(("next.jdbc", "data"), frameworks)
            self.assertIn(("stuartsierra-component", "runtime"), frameworks)

            routes = {(route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("GET", "/", "user-ctl/index"), routes)
            self.assertIn(("GET", "/users/{id}", "user-ctl/show"), routes)
            self.assertIn(("POST", "/users/save", "user-ctl/save"), routes)
            user_route = next(route for route in facts.api_routes if route.path == "/users/{id}")
            self.assertEqual(["id"], [param.name for param in user_route.parameters])
            post_route = next(route for route in facts.api_routes if route.path == "/users/save")
            self.assertEqual("params", post_route.request_body)

            models = {(model.name, model.kind) for model in facts.data_models}
            self.assertIn(("Application", "clojure-record"), models)
            self.assertIn(("Database", "clojure-record"), models)
            self.assertIn(("my-db", "clojure-db-spec"), models)
            self.assertIn(("user-manager", "clojure-namespace-model"), models)

            data_layers = {(layer.kind, layer.name): layer.details for layer in facts.data_layers}
            self.assertNotIn(("clojure-jdbc-data", "main"), data_layers)
            clojure_layer = data_layers[("clojure-jdbc-data", "user_manager")]
            self.assertIn("library:next.jdbc", clojure_layer)
            self.assertIn("dbtype:sqlite", clojure_layer)
            self.assertIn("table:users", clojure_layer)
            self.assertIn("query-table:users", clojure_layer)
            self.assertIn("write-table:users", clojure_layer)

            test_maps = {test_map.test_path: test_map for test_map in facts.test_maps}
            model_test = test_maps["test/demo/model/user_manager_test.clj"]
            self.assertEqual("data-model", model_test.target_kind)
            self.assertEqual("user-manager", model_test.target)
            self.assertEqual("high", model_test.confidence)


if __name__ == "__main__":
    unittest.main()
