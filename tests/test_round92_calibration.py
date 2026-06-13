from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round92VaporSwiftCalibrationTests(unittest.TestCase):
    def test_vapor_routes_contracts_entrypoint_and_fluent_models_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Package.swift").write_text(
                """
// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "VaporDemo",
    products: [
        .executable(name: "Run", targets: ["Run"]),
    ],
    dependencies: [
        .package(url: "https://github.com/vapor/vapor", from: "4.0.0"),
        .package(url: "https://github.com/vapor/fluent-mysql-driver", from: "4.0.0"),
    ],
    targets: [
        .executableTarget(name: "Run", dependencies: [
            .product(name: "Vapor", package: "vapor"),
            .product(name: "FluentMySQLDriver", package: "fluent-mysql-driver"),
        ]),
        .testTarget(name: "RunTests", dependencies: ["Run"]),
    ]
)
""".strip()
                + "\n",
                encoding="utf-8",
            )

            run = root / "Sources" / "Run"
            run.mkdir(parents=True)
            (run / "main.swift").write_text(
                """
import Vapor

try applicationMain()
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (run / "ApplicationMain.swift").write_text(
                """
import Vapor

public func applicationMain() throws {
    let articles = ArticlesController()
    let tags = TagsController()

    useCase.routing(collections: [
        .init(method: .get, paths: ["tags"], closure: tags.index),
        .init(method: .post, paths: ["articles"], closure: articles.create),
        .init(method: .get, paths: ["articles", ":slug"], closure: articles.show)
    ])
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            controllers = run / "Controllers"
            controllers.mkdir()
            (controllers / "ArticlesController.swift").write_text(
                """
import Vapor

struct ArticlesController {
    func create(_ request: Request) throws -> Future<Response> {
        let req = try request.content.decode(NewArticleRequest.self)
        return try Response(req)
    }

    func show(_ request: Request) throws -> Future<Response> {
        guard let slug = request.parameters.get("slug") else {
            throw Abort(.badRequest)
        }
        let preview = request.query[String.self, at: "preview"]
        return try Response(preview ?? slug)
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (controllers / "TagsController.swift").write_text(
                """
import Vapor

struct TagsController {
    func index(_ request: Request) throws -> Future<Response> {
        return try Response(TagsResponse(tags: []))
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            models = run / "Models"
            models.mkdir()
            (models / "Articles.swift").write_text(
                """
import FluentKit

public final class Articles: Model {
    public static let schema = "articles"

    @ID(custom: .id, generatedBy: .database)
    public var id: Int?

    @Field(key: "slug")
    public var slug: String

    @Parent(key: "author")
    public var author: Users

    @Children(for: \\.$article)
    public var comments: [Comments]

    public init() {}

    public static func create(on database: MySQLDatabase) -> EventLoopFuture<Void> {
        database.query(\"\"\"
            CREATE TABLE IF NOT EXISTS `articles` (
              `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
              `slug` varchar(100) NOT NULL,
              PRIMARY KEY (`id`),
              UNIQUE KEY `slug_UNIQUE` (`slug`)
            );
            \"\"\").map { _ in return }
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (models / "Requests.swift").write_text(
                """
struct NewArticleRequest: Codable {
    let title: String
}

struct TagsResponse: Codable {
    let tags: [String]
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            test_dir = root / "Tests" / "RunTests"
            test_dir.mkdir(parents=True)
            (test_dir / "TagsTests.swift").write_text(
                """
import XCTest

final class TagsTests: XCTestCase {
    func testTagsRoute() throws {
        try app.test(.GET, "/tags")
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("vapor", "backend"), frameworks)
            self.assertIn(("fluent", "data"), frameworks)

            entrypoints = {(entrypoint.kind, entrypoint.path, entrypoint.command) for entrypoint in facts.entrypoints}
            self.assertIn(("vapor-app", "Sources/Run/main.swift", "swift run Run"), entrypoints)

            commands = {command.name for command in facts.commands}
            self.assertIn("swift build", commands)
            self.assertIn("swift test", commands)
            self.assertIn("swift run Run", commands)

            routes = {(route.method, route.path, route.handler): route for route in facts.api_routes}
            self.assertIn(("GET", "/tags", "tags.index"), routes)
            self.assertIn(("POST", "/articles", "articles.create"), routes)
            self.assertIn(("GET", "/articles/:slug", "articles.show"), routes)
            self.assertEqual("content", routes[("POST", "/articles", "articles.create")].request_body)
            self.assertIn("slug", [param.name for param in routes[("GET", "/articles/:slug", "articles.show")].parameters])

            data_models = {(model.name, model.kind): model for model in facts.data_models}
            article = data_models[("Articles", "fluent-model")]
            self.assertIn("slug:String", article.fields)
            self.assertIn("table:articles", article.annotations)
            self.assertIn("relation:parent:author:Users", article.annotations)

            data_layers = {(layer.kind, layer.name): layer.details for layer in facts.data_layers}
            fluent = data_layers[("fluent-model", "Articles")]
            self.assertIn("table:articles", fluent)
            self.assertIn("column:slug", fluent)
            self.assertIn("relation:parent:author:Users", fluent)
            self.assertIn("sql-column:slug", fluent)

            contracts = {(contract.method, contract.path, contract.framework): contract for contract in facts.api_contracts}
            create_contract = contracts[("POST", "/articles", "vapor")]
            self.assertIn("body:NewArticleRequest", create_contract.request_hints)
            self.assertIn("response:Response", create_contract.response_hints)
            show_contract = contracts[("GET", "/articles/:slug", "vapor")]
            self.assertIn("path:slug", show_contract.request_hints)
            self.assertIn("query:preview:String", show_contract.request_hints)

            test_maps = {test_map.test_path: test_map for test_map in facts.test_maps}
            tags_test = test_maps["Tests/RunTests/TagsTests.swift"]
            self.assertEqual("api-route", tags_test.target_kind)
            self.assertEqual("GET /tags", tags_test.target)


if __name__ == "__main__":
    unittest.main()
