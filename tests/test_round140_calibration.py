from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round140DiscourseNoiseCalibrationTests(unittest.TestCase):
    def test_auth_words_and_generic_service_symbols_do_not_create_false_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            controllers = root / "frontend" / "app" / "controllers" / "invites"
            emoji = root / "frontend" / "pretty-text" / "addon" / "emoji"
            services = root / "app" / "services"
            controllers.mkdir(parents=True)
            emoji.mkdir(parents=True)
            services.mkdir(parents=True)

            (controllers / "show.js").write_text(
                """
export default class InvitesShowController {
  authOptions = null;
  get accountEmail() {
    return this.model?.email;
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (emoji / "data.js").write_text(
                'export const emojis = new Set(["passport_control", "customs"]);\n',
                encoding="utf-8",
            )
            (services / "const.rb").write_text("class const\nend\n", encoding="utf-8")
            (services / "helper.rb").write_text("class Helper\nend\n", encoding="utf-8")
            (services / "user_service.rb").write_text("class UserService\nend\n", encoding="utf-8")

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertNotIn("nextauth", frameworks)
            self.assertNotIn("passport", frameworks)

            services_by_name = {service.name for service in facts.services}
            self.assertIn("UserService", services_by_name)
            self.assertNotIn("const", services_by_name)
            self.assertNotIn("Helper", services_by_name)


if __name__ == "__main__":
    unittest.main()
