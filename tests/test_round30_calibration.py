from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round30SymfonyCalibrationTests(unittest.TestCase):
    def test_symfony_attribute_routes_keep_neighbor_attributes_and_yaml_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "composer.json").write_text(
                '{"require":{"symfony/framework-bundle":"^7.0","symfony/routing":"^7.0"}}\n',
                encoding="utf-8",
            )
            config = root / "config"
            config.mkdir()
            (config / "routes.yaml").write_text(
                """
homepage:
    path: /{_locale}
    controller: Symfony\\Bundle\\FrameworkBundle\\Controller\\TemplateController::templateAction

controllers:
    resource: routing.controllers
    prefix: /{_locale}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            controllers = root / "src" / "Controller"
            admin = controllers / "Admin"
            admin.mkdir(parents=True)
            (controllers / "BlogController.php").write_text(
                """
<?php

use Symfony\\Component\\Routing\\Attribute\\Route;

#[Route('/blog')]
final class BlogController
{
    #[Route('/', name: 'blog_index', methods: ['GET'])]
    #[Route('/rss.xml', name: 'blog_rss', methods: ['GET'])]
    #[Cache(smaxage: 10)]
    public function index() {}

    #[Route('/comment/{postSlug}/new', methods: ['POST'])]
    #[IsGranted('IS_AUTHENTICATED')]
    public function commentNew() {}
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (controllers / "UserController.php").write_text(
                """
<?php

use Symfony\\Component\\Routing\\Attribute\\Route;

#[Route('/profile'), IsGranted('ROLE_USER')]
final class UserController
{
    #[Route('/edit', name: 'user_edit', methods: ['GET', 'POST'])]
    public function edit() {}
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (admin / "BlogController.php").write_text(
                """
<?php

use Symfony\\Component\\Routing\\Attribute\\Route;

#[Route('/admin/post')]
#[IsGranted('ROLE_ADMIN')]
final class BlogController
{
    #[Route('/{id:post}/edit', methods: ['GET', 'POST'])]
    #[IsGranted('edit', subject: 'post')]
    public function edit() {}
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.framework, route.kind, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("symfony", "symfony-yaml-route", "ANY", "/{_locale}", "Symfony\\Bundle\\FrameworkBundle\\Controller\\TemplateController::templateAction"), routes)
            self.assertIn(("symfony", "symfony-attribute-route", "GET", "/{_locale}/blog", "index"), routes)
            self.assertIn(("symfony", "symfony-attribute-route", "GET", "/{_locale}/blog/rss.xml", "index"), routes)
            self.assertIn(("symfony", "symfony-attribute-route", "POST", "/{_locale}/blog/comment/{postSlug}/new", "commentNew"), routes)
            self.assertIn(("symfony", "symfony-attribute-route", "GET", "/{_locale}/profile/edit", "edit"), routes)
            self.assertIn(("symfony", "symfony-attribute-route", "POST", "/{_locale}/profile/edit", "edit"), routes)
            self.assertIn(("symfony", "symfony-attribute-route", "GET", "/{_locale}/admin/post/{id:post}/edit", "edit"), routes)
            self.assertIn(("symfony", "symfony-attribute-route", "POST", "/{_locale}/admin/post/{id:post}/edit", "edit"), routes)
            self.assertFalse(any(route.path == "/admin/post/{id:post}/edit" for route in facts.api_routes))
            self.assertTrue(all(route.evidence.file and route.evidence.line_start for route in facts.api_routes if route.framework == "symfony"))


if __name__ == "__main__":
    unittest.main()
