from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round26CalibrationTests(unittest.TestCase):

    def test_scan_project_extracts_aspnet_razor_pages_without_partial_route_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pages = root / "src" / "Web" / "Pages" / "Basket"
            pages.mkdir(parents=True)
            (pages / "Index.cshtml").write_text(
                """
@page "{handler?}"
@model IndexModel
<form method="post" asp-page="/Basket/Index" asp-page-handler="Update">
  <input type="number" name="Items[0].Quantity" value="1" />
  <button type="submit">Update</button>
</form>
<a asp-page="/Index">Continue</a>
<img src="~/images/main_banner_text.png" />
""".strip()
                + "\n",
                encoding="utf-8",
            )
            identity = root / "src" / "Web" / "Areas" / "Identity" / "Pages" / "Account"
            identity.mkdir(parents=True)
            (identity / "Login.cshtml").write_text(
                """
@page
<form method="post" asp-page="/Account/Login">
  <input name="Input.Email" />
</form>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            shared = root / "src" / "Web" / "Views" / "Shared"
            shared.mkdir(parents=True)
            (shared / "_Layout.cshtml").write_text(
                """
<link rel="stylesheet" href="~/css/app.css" asp-fallback-href="~/lib/bootstrap/dist/css/bootstrap.min.css" />
<script src="~/js/site.js" asp-fallback-src="~/lib/jquery/dist/jquery.min.js"></script>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            blazor_pages = root / "src" / "BlazorAdmin" / "Pages"
            blazor_pages.mkdir(parents=True)
            (blazor_pages / "Logout.razor").write_text(
                """
@page "/logout"
<img src="@LoadPicture" />
""".strip()
                + "\n",
                encoding="utf-8",
            )
            blazor_shared = root / "src" / "BlazorAdmin" / "Shared"
            blazor_shared.mkdir(parents=True)
            (blazor_shared / "NavMenu.razor").write_text(
                """
<nav>
  <a href="admin">Home</a>
</nav>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            controllers = root / "src" / "Web" / "Controllers"
            controllers.mkdir(parents=True)
            (controllers / "OrderController.cs").write_text(
                """
using Microsoft.AspNetCore.Mvc;

[Route("[controller]")]
public class OrderController : Controller
{
    [HttpGet("")]
    public IActionResult MyOrders() => View();
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            functional = root / "tests" / "FunctionalTests" / "Web" / "Controllers"
            functional.mkdir(parents=True)
            (functional / "OrderControllerIndex.cs").write_text(
                "public class OrderControllerIndex { }\n",
                encoding="utf-8",
            )
            domain = root / "tests" / "UnitTests" / "ApplicationCore" / "Entities" / "OrderTests"
            domain.mkdir(parents=True)
            (domain / "OrderTotal.cs").write_text(
                "public class OrderTotal { }\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {page.route.lower(): page for page in facts.pages}
            self.assertIn("/basket", routes)
            self.assertIn("/identity/account/login", routes)
            self.assertIn("/logout", routes)
            self.assertNotIn("/shared/_layout", routes)
            self.assertNotIn("/src/blazoradmin/shared/navmenu", routes)

            forms = {(form.source, form.method, form.action, tuple(form.fields)) for form in facts.forms}
            self.assertIn(
                (
                    "src/Web/Pages/Basket/Index.cshtml",
                    "POST",
                    "/Basket/Index?handler=Update",
                    ("Items[0].Quantity",),
                ),
                forms,
            )
            assets = {(asset.source, asset.asset_path, asset.usage_kind) for asset in facts.assets}
            self.assertIn(("src/Web/Views/Shared/_Layout.cshtml", "~/css/app.css", "link-href"), assets)
            self.assertIn(("src/Web/Views/Shared/_Layout.cshtml", "~/lib/bootstrap/dist/css/bootstrap.min.css", "asp-fallback-href"), assets)
            self.assertIn(("src/Web/Views/Shared/_Layout.cshtml", "~/js/site.js", "script-src"), assets)
            self.assertNotIn(("src/BlazorAdmin/Pages/Logout.razor", "@LoadPicture", "img-src"), assets)

            tests = {item.test_path: (item.target_kind, item.target) for item in facts.test_maps}
            self.assertEqual(
                ("api-route", "GET /order"),
                tests["tests/FunctionalTests/Web/Controllers/OrderControllerIndex.cs"],
            )
            self.assertNotEqual(
                ("api-route", "GET /order"),
                tests["tests/UnitTests/ApplicationCore/Entities/OrderTests/OrderTotal.cs"],
            )


if __name__ == "__main__":
    unittest.main()
