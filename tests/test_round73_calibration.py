from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round73DotNetCalibrationTests(unittest.TestCase):
    def test_dotnet_entrypoints_commands_and_efcore_framework_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            web = root / "src" / "Web"
            blazor = root / "src" / "BlazorAdmin"
            tests = root / "tests" / "Web.Tests"
            web.mkdir(parents=True)
            (blazor / "Services").mkdir(parents=True)
            tests.mkdir(parents=True)
            (root / "Demo.sln").write_text(
                "Microsoft Visual Studio Solution File, Format Version 12.00\n",
                encoding="utf-8",
            )
            (web / "Web.csproj").write_text(
                """
<Project Sdk="Microsoft.NET.Sdk.Web">
  <ItemGroup>
    <PackageReference Include="Microsoft.EntityFrameworkCore.SqlServer" Version="8.0.0" />
  </ItemGroup>
</Project>
""".strip(),
                encoding="utf-8",
            )
            (web / "Program.cs").write_text(
                """
using Microsoft.AspNetCore.Builder;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddDbContext<AppDbContext>();
var app = builder.Build();
app.MapGet("/health", () => "ok");
app.MapPost("/user/Logout", () => "ok");
app.Run();
""".strip(),
                encoding="utf-8",
            )
            (blazor / "BlazorAdmin.csproj").write_text(
                """
<Project Sdk="Microsoft.NET.Sdk.BlazorWebAssembly">
  <ItemGroup>
    <PackageReference Include="Microsoft.AspNetCore.Components.WebAssembly" Version="8.0.0" />
  </ItemGroup>
</Project>
""".strip(),
                encoding="utf-8",
            )
            (blazor / "Services" / "CatalogItemService.cs").write_text(
                """
namespace BlazorAdmin.Services;

public class CatalogItemService
{
    private readonly HttpService _httpService;
    private readonly HttpClient HttpClient;

    public Task Create(CreateCatalogItemRequest request)
    {
        return _httpService.HttpPost<CreateCatalogItemResponse>("catalog-items", request);
    }

    public Task Read(int id)
    {
        return _httpService.HttpGet<EditCatalogItemResult>($"catalog-items/{id}");
    }

    public Task Delete(int catalogItemId)
    {
        return _httpService.HttpDelete<DeleteCatalogItemResponse>("catalog-items", catalogItemId);
    }

    public Task Logout()
    {
        return HttpClient.PostAsync("User/Logout", null);
    }
}
""".strip(),
                encoding="utf-8",
            )
            (tests / "Web.Tests.csproj").write_text(
                """
<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.0.0" />
  </ItemGroup>
</Project>
""".strip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            entrypoints = {(entry.kind, entry.path, entry.command) for entry in facts.entrypoints}
            self.assertIn(
                (
                    "dotnet-program",
                    "src/Web/Program.cs",
                    "dotnet run --project src/Web/Web.csproj",
                ),
                entrypoints,
            )

            commands = {(command.name, tuple(command.arguments), command.path) for command in facts.commands}
            self.assertIn(("dotnet build", ("Demo.sln",), "Demo.sln"), commands)
            self.assertIn(("dotnet test", ("Demo.sln",), "Demo.sln"), commands)
            self.assertIn(("dotnet run", ("--project", "src/BlazorAdmin/BlazorAdmin.csproj"), "src/BlazorAdmin/BlazorAdmin.csproj"), commands)
            self.assertIn(("dotnet run", ("--project", "src/Web/Web.csproj"), "src/Web/Web.csproj"), commands)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("aspnetcore", "backend"), frameworks)
            self.assertIn(("ef-core", "data"), frameworks)

            api_calls = {(call.method, call.endpoint, call.context) for call in facts.api_calls}
            self.assertIn(("POST", "/api/catalog-items", "csharp-http-service"), api_calls)
            self.assertIn(("GET", "/api/catalog-items/{id}", "csharp-http-service"), api_calls)
            self.assertIn(("DELETE", "/api/catalog-items/{catalogItemId}", "csharp-http-service"), api_calls)
            self.assertIn(("POST", "/User/Logout", "csharp-httpclient"), api_calls)
            self.assertNotIn(("DELETE", "dynamic:id", "source-variable"), api_calls)

            logout_link = next(link for link in facts.api_links if link.endpoint == "/User/Logout")
            self.assertEqual("/user/Logout", logout_link.matched_route)
            self.assertEqual("case-insensitive", logout_link.match_type)


if __name__ == "__main__":
    unittest.main()
