from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round89PlayScalaCalibrationTests(unittest.TestCase):
    def test_play_scala_sbt_routes_models_data_and_tests_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "build.sbt").write_text(
                """
lazy val root = (project in file(".")).enablePlugins(PlayScala)

libraryDependencies ++= Seq(
  guice,
  "com.typesafe.play" %% "play-slick" % "6.0.0",
  "org.postgresql" % "postgresql" % "42.7.3"
)
""".strip()
                + "\n",
                encoding="utf-8",
            )
            conf = root / "conf"
            conf.mkdir()
            (conf / "routes").write_text(
                """
GET     /                           controllers.HomeController.index()
GET     /computers                  controllers.HomeController.list(p:Int ?= 0, s ?= "name")
GET     /computers/:id              controllers.HomeController.show(id:Long)
POST    /computers                  controllers.HomeController.save(request: Request)
GET     /assets/*file               controllers.Assets.versioned(path="/public", file: Asset)
""".strip()
                + "\n",
                encoding="utf-8",
            )

            controllers = root / "app" / "controllers"
            models = root / "app" / "models"
            views = root / "app" / "views"
            controllers.mkdir(parents=True)
            models.mkdir(parents=True)
            views.mkdir(parents=True)
            (controllers / "HomeController.scala").write_text(
                """
package controllers

import javax.inject._
import play.api.mvc._
import models.Computer

@Singleton
class HomeController @Inject()(cc: ControllerComponents) extends AbstractController(cc) {
  def index() = Action { Ok(views.html.index()) }
  def list(p: Int, s: String) = Action { Ok("list") }
  def show(id: Long) = Action { Ok(id.toString) }
  def save(request: Request[AnyContent]) = Action { Created }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (models / "Computer.scala").write_text(
                """
package models

import play.api.libs.json.Json
import slick.jdbc.PostgresProfile.api._

case class Computer(id: Option[Long] = None, name: String, companyId: Option[Long] = None)

object Computer {
  implicit val format = Json.format[Computer]
}

class Computers(tag: Tag) extends Table[Computer](tag, "COMPUTER") {
  def id = column[Long]("ID", O.PrimaryKey)
  def name = column[String]("NAME")
  def * = (id.?, name, companyId.?) <> (Computer.tupled, Computer.unapply)
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (views / "index.scala.html").write_text(
                """
@(message: String = "Hello")
<html>
  <head><title>Demo</title></head>
  <body>@message</body>
</html>
""".strip()
                + "\n",
                encoding="utf-8",
            )

            test_dir = root / "test" / "controllers"
            test_dir.mkdir(parents=True)
            (test_dir / "HomeControllerSpec.scala").write_text(
                """
package controllers

import org.scalatestplus.play._
import play.api.test._
import play.api.test.Helpers._

class HomeControllerSpec extends PlaySpec {
  "HomeController list" should {
    "render computers" in {
      route(app, FakeRequest(GET, "/computers")).map(status) mustBe Some(OK)
    }
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            files = {file.path: (file.language, file.role) for file in facts.files}
            self.assertEqual(("scala-build", "config"), files["build.sbt"])
            self.assertEqual(("play-routes", "api"), files["conf/routes"])
            self.assertEqual(("scala", "api"), files["app/controllers/HomeController.scala"])
            self.assertEqual(("twirl", "frontend-page"), files["app/views/index.scala.html"])

            dependencies = {(dependency.name, dependency.scope, dependency.source) for dependency in facts.dependencies}
            self.assertIn(("playframework/play-scala", "sbt-plugin", "build.sbt"), dependencies)
            self.assertIn(("com.typesafe.play/play-slick", "sbt", "build.sbt"), dependencies)
            self.assertIn(("play:guice", "sbt", "build.sbt"), dependencies)

            commands = {command.name for command in facts.commands}
            self.assertIn("sbt run", commands)
            self.assertIn("sbt test", commands)
            self.assertIn("sbt routes", commands)

            entrypoints = {(entrypoint.kind, entrypoint.path, entrypoint.command) for entrypoint in facts.entrypoints}
            self.assertIn(("play-app", "conf/routes", "sbt run"), entrypoints)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("playframework", "backend"), frameworks)
            self.assertIn(("play-slick", "data"), frameworks)

            routes = {(route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("GET", "/", "controllers.HomeController.index"), routes)
            self.assertIn(("GET", "/computers", "controllers.HomeController.list"), routes)
            self.assertIn(("GET", "/computers/{id}", "controllers.HomeController.show"), routes)
            self.assertIn(("POST", "/computers", "controllers.HomeController.save"), routes)
            self.assertIn(("GET", "/assets/{file}", "controllers.Assets.versioned"), routes)
            show_route = next(route for route in facts.api_routes if route.path == "/computers/{id}")
            self.assertEqual(["id"], [param.name for param in show_route.parameters])
            list_route = next(route for route in facts.api_routes if route.handler == "controllers.HomeController.list")
            self.assertIn(("p", "query", "Int", False), [(param.name, param.source, param.type, param.required) for param in list_route.parameters])
            post_route = next(route for route in facts.api_routes if route.method == "POST" and route.path == "/computers")
            self.assertEqual("request", post_route.request_body)

            models = {(model.name, model.kind): model for model in facts.data_models}
            self.assertIn(("Computer", "scala-case-class"), models)
            self.assertIn("name:String", models[("Computer", "scala-case-class")].fields)
            self.assertIn("json-format", models[("Computer", "scala-case-class")].annotations)

            data_layers = {(layer.kind, layer.name): layer.details for layer in facts.data_layers}
            scala_layer = data_layers[("scala-data", "Computer")]
            self.assertIn("library:slick", scala_layer)
            self.assertIn("table:COMPUTER", scala_layer)

            test_maps = {test_map.test_path: test_map for test_map in facts.test_maps}
            controller_test = test_maps["test/controllers/HomeControllerSpec.scala"]
            self.assertEqual("api-route", controller_test.target_kind)
            self.assertEqual("GET /computers", controller_test.target)
            self.assertEqual("high", controller_test.confidence)


if __name__ == "__main__":
    unittest.main()
