from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round108DotnetRazorBlazorCalibrationTests(unittest.TestCase):
    def test_aspnet_razor_pages_do_not_inherit_blazor_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "App.csproj").write_text(
                """
<Project Sdk="Microsoft.NET.Sdk.Web">
  <ItemGroup>
    <PackageReference Include="Microsoft.AspNetCore.Blazor" Version="0.7.0" />
  </ItemGroup>
</Project>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            blazor_pages = root / "src" / "BlazorAdmin" / "Pages"
            razor_pages = root / "src" / "Web" / "Pages"
            razor_views = root / "src" / "Web" / "Views" / "Shared"
            blazor_pages.mkdir(parents=True)
            razor_pages.mkdir(parents=True)
            razor_views.mkdir(parents=True)
            (blazor_pages / "List.razor").write_text(
                '\ufeff@page "/admin"\n<h1>Admin</h1>\n',
                encoding="utf-8",
            )
            (razor_pages / "Index.cshtml").write_text(
                "@page\n<h1>Home</h1>\n",
                encoding="utf-8",
            )
            (razor_views / "_Layout.cshtml").write_text(
                "<main>@RenderBody()</main>\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.framework, route.kind, route.route, route.path) for route in facts.frontend_routes}
            self.assertIn(("blazor", "blazor-page-route", "/admin", "src/BlazorAdmin/Pages/List.razor"), routes)
            self.assertIn(("razor", "template-page-route", "/", "src/Web/Pages/Index.cshtml"), routes)
            self.assertNotIn(("razor", "template-page-route", "/admin", "src/BlazorAdmin/Pages/List.razor"), routes)
            self.assertNotIn(("blazor", "blazor-page-route", "/", "src/Web/Pages/Index.cshtml"), routes)

            components = {(component.framework, component.name, component.path) for component in facts.components}
            self.assertIn(("blazor", "List", "src/BlazorAdmin/Pages/List.razor"), components)
            self.assertIn(("razor", "Index", "src/Web/Pages/Index.cshtml"), components)
            self.assertNotIn(("blazor", "Index", "src/Web/Pages/Index.cshtml"), components)


if __name__ == "__main__":
    unittest.main()
