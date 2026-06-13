from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round123AspNetCoreCalibrationTests(unittest.TestCase):

    def test_primary_constructor_controller_merges_class_route_and_domain_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            features = root / "src" / "Conduit" / "Features" / "Articles"
            domain = root / "src" / "Conduit" / "Domain"
            features.mkdir(parents=True)
            domain.mkdir(parents=True)
            (root / "src" / "Conduit" / "Conduit.csproj").parent.mkdir(parents=True, exist_ok=True)
            (root / "src" / "Conduit" / "Conduit.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk.Web"><ItemGroup><PackageReference Include="Microsoft.AspNetCore.OpenApi" /></ItemGroup></Project>\n',
                encoding="utf-8",
            )
            (features / "ArticlesController.cs").write_text(
                """
using Microsoft.AspNetCore.Mvc;

namespace Conduit.Features.Articles;

[Route("articles")]
public class ArticlesController(IMediator mediator) : Controller
{
    [HttpGet]
    public Task<ArticlesEnvelope> Get(CancellationToken cancellationToken) => mediator.Send(new List.Query(), cancellationToken);

    [HttpGet("{slug}")]
    public Task<ArticleEnvelope> Get(string slug, CancellationToken cancellationToken) => mediator.Send(new Details.Query(slug), cancellationToken);

    [HttpPost]
    public Task<ArticleEnvelope> Create([FromBody] Create.Command command, CancellationToken cancellationToken) => mediator.Send(command, cancellationToken);
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (domain / "Article.cs").write_text(
                """
namespace Conduit.Domain;

public class Article
{
    public int ArticleId { get; init; }
    public string? Slug { get; set; }
    public string? Title { get; set; }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.method, route.path, route.handler, route.kind) for route in facts.api_routes}
            self.assertIn(("GET", "/articles", "Get", "aspnetcore-route"), routes)
            self.assertIn(("GET", "/articles/{slug}", "Get", "aspnetcore-route"), routes)
            self.assertIn(("POST", "/articles", "Create", "aspnetcore-route"), routes)
            self.assertFalse(any(route.handler == "ArticlesController" for route in facts.api_routes))

            models = {(model.name, model.kind, model.path): model for model in facts.data_models}
            article = models[("Article", "csharp-entity", "src/Conduit/Domain/Article.cs")]
            self.assertIn("ArticleId:int", article.fields)
            self.assertIn("Slug:string?", article.fields)
            self.assertIn("Title:string?", article.fields)


if __name__ == "__main__":
    unittest.main()
