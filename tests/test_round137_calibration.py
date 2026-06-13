from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round137RazorFormFieldCalibrationTests(unittest.TestCase):
    def test_razor_tag_helpers_and_html_helpers_are_form_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            views = root / "src" / "Plugins" / "Nop.Plugin.ExternalAuth.Facebook" / "Views"
            views.mkdir(parents=True)
            (root / "src" / "Nop.Web" / "Nop.Web.csproj").parent.mkdir(parents=True)
            (root / "src" / "Nop.Web" / "Nop.Web.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>\n',
                encoding="utf-8",
            )
            (views / "Configure.cshtml").write_text(
                """
@model ConfigurationModel

<form asp-controller="FacebookAuthentication" asp-action="Configure" method="post">
  <nop-editor asp-for="ClientId" />
  <nop-editor asp-for="ClientSecret" />
  <nop-select asp-for="AccountTypeId" asp-items="Model.AccountTypes" />
  <nop-textarea asp-for="TrackingScript" />
  <nop-override-store-checkbox asp-for="Enabled_OverrideForStore" asp-input="Enabled" />
  <input asp-for="Token" type="hidden" />
  <input asp-for="NewsLetterSubscriptionTypes[i].TypeId" type="hidden" />
  <textarea asp-for="Description"></textarea>
  @Html.HiddenFor(model => model.Locales[item].LanguageId)
  @Html.EditorFor(model => model.ApiKey)
</form>
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            form = next(item for item in facts.forms if item.source.endswith("Configure.cshtml"))
            self.assertEqual("POST", form.method)
            self.assertEqual("/FacebookAuthentication/Configure", form.action)
            self.assertEqual(
                [
                    "Token",
                    "NewsLetterSubscriptionTypes[].TypeId",
                    "Description",
                    "ClientId",
                    "ClientSecret",
                    "AccountTypeId",
                    "TrackingScript",
                    "Enabled_OverrideForStore",
                    "Locales[].LanguageId",
                    "ApiKey",
                ],
                form.fields,
            )


if __name__ == "__main__":
    unittest.main()
