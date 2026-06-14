from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round134HeexFormCalibrationTests(unittest.TestCase):
    def test_heex_component_form_fields_are_extracted_without_cross_form_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            templates = root / "lib" / "demo_web" / "templates" / "auth"
            templates.mkdir(parents=True)
            (root / "mix.exs").write_text(
                """
defmodule Demo.MixProject do
  use Mix.Project
  defp deps do
    [{:phoenix, "~> 1.7"}, {:phoenix_live_view, "~> 0.20"}]
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (templates / "login.html.heex").write_text(
                """
<.form :let={f} for={@conn} action="/login">
  <.input type="email" field={f[:email]} />
  <.input type="password" field={f[:password]} />
  <.input type="hidden" field={f[:return_to]} />
</.form>

<.form action="/mfa" method="post">
  <.input name="totp_code" />
</.form>
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            forms = {(form.action, form.method, tuple(form.fields)) for form in facts.forms}
            self.assertIn(("/login", "POST", ("email", "password", "return_to")), forms)
            self.assertIn(("/mfa", "POST", ("totp_code",)), forms)


if __name__ == "__main__":
    unittest.main()
