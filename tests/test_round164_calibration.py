from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round164RazorAdminAreaCalibrationTests(unittest.TestCase):
    def test_razor_admin_layout_infers_admin_area_for_tag_helper_forms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Plugin.csproj").write_text(
                """
<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup>
</Project>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            controller_dir = root / "src" / "Plugins" / "Nop.Plugin.ExternalAuth.Facebook" / "Controllers"
            view_dir = root / "src" / "Plugins" / "Nop.Plugin.ExternalAuth.Facebook" / "Views"
            controller_dir.mkdir(parents=True)
            view_dir.mkdir(parents=True)
            (controller_dir / "FacebookAuthenticationController.cs").write_text(
                """
using Microsoft.AspNetCore.Mvc;

namespace Nop.Plugin.ExternalAuth.Facebook.Controllers;

[Area("Admin")]
public class FacebookAuthenticationController : Controller
{
    [HttpPost]
    public IActionResult Configure() => Ok();
}
""".lstrip(),
                encoding="utf-8",
            )
            (view_dir / "Configure.cshtml").write_text(
                """
@model ConfigurationModel
@{
    Layout = "_ConfigurePlugin";
}
<form asp-controller="FacebookAuthentication" asp-action="Configure" method="post">
    <input asp-for="ClientId" />
</form>
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            forms = {(form.method, form.action, form.source) for form in facts.forms}
            self.assertIn(
                (
                    "POST",
                    "/Admin/FacebookAuthentication/Configure",
                    "src/Plugins/Nop.Plugin.ExternalAuth.Facebook/Views/Configure.cshtml",
                ),
                forms,
            )

            calls = {(call.method, call.endpoint, call.matched_route) for call in facts.api_calls}
            self.assertIn(
                (
                    "POST",
                    "/Admin/FacebookAuthentication/Configure",
                    "POST /Admin/FacebookAuthentication/Configure",
                ),
                calls,
            )


if __name__ == "__main__":
    unittest.main()
