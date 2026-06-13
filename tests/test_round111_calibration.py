from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round111SymfonyCalibrationTests(unittest.TestCase):
    def test_symfony_entrypoints_commands_doctrine_models_and_twig_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "composer.json").write_text(
                """
{
  "require": {
    "symfony/framework-bundle": "^8.0",
    "symfony/console": "^8.0",
    "symfony/twig-bundle": "^8.0",
    "doctrine/orm": "^3.5"
  },
  "require-dev": {
    "doctrine/doctrine-fixtures-bundle": "^4.1",
    "phpunit/phpunit": "^11.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "public").mkdir()
            (root / "public" / "index.php").write_text("<?php\nuse App\\Kernel;\n", encoding="utf-8")
            (root / "bin").mkdir()
            (root / "bin" / "console").write_text("#!/usr/bin/env php\n<?php\n", encoding="utf-8")
            (root / "config").mkdir()
            (root / "config" / "bundles.php").write_text("<?php\nreturn [];\n", encoding="utf-8")
            (root / "phpunit.dist.xml").write_text("<phpunit />\n", encoding="utf-8")
            (root / "src" / "Entity").mkdir(parents=True)
            (root / "src" / "Entity" / "Post.php").write_text(
                """
<?php
namespace App\\Entity;

use App\\Repository\\PostRepository;
use Doctrine\\DBAL\\Types\\Types;
use Doctrine\\ORM\\Mapping as ORM;
use Symfony\\Component\\Validator\\Constraints as Assert;

#[ORM\\Entity(repositoryClass: PostRepository::class)]
#[ORM\\Table(name: 'symfony_demo_post')]
class Post
{
    #[ORM\\Id]
    #[ORM\\GeneratedValue]
    #[ORM\\Column(type: Types::INTEGER)]
    private ?int $id = null;

    #[ORM\\Column(type: Types::STRING)]
    #[Assert\\NotBlank]
    private ?string $title = null;

    #[ORM\\ManyToOne(targetEntity: User::class)]
    private ?User $author = null;

    #[ORM\\ManyToMany(targetEntity: Tag::class, cascade: ['persist'])]
    #[ORM\\JoinTable(name: 'post_tag')]
    #[ORM\\OrderBy(['name' => 'ASC'])]
    private Collection $tags;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            templates = root / "templates" / "blog"
            templates.mkdir(parents=True)
            (templates / "index.html.twig").write_text("<main>Blog</main>\n", encoding="utf-8")
            (templates / "_form.html.twig").write_text("<form method=\"post\"></form>\n", encoding="utf-8")
            (root / "templates" / "base.html.twig").write_text("<html><body></body></html>\n", encoding="utf-8")

            facts = scan_project(root)

            entrypoints = {(entry.kind, entry.path, entry.command) for entry in facts.entrypoints}
            self.assertIn(("symfony-front-controller", "public/index.php", "symfony server:start"), entrypoints)
            self.assertIn(("symfony-console", "bin/console", "php bin/console"), entrypoints)

            commands = {command.name for command in facts.commands}
            self.assertIn("symfony server:start", commands)
            self.assertIn("php bin/console", commands)
            self.assertIn("php bin/console debug:router", commands)
            self.assertIn("php bin/console doctrine:fixtures:load", commands)
            self.assertIn("vendor/bin/phpunit", commands)

            doctrine_models = {model.name: model for model in facts.data_models if model.kind == "doctrine-entity"}
            self.assertIn("Post", doctrine_models)
            self.assertIn("id:?int", doctrine_models["Post"].fields)
            self.assertIn("title:?string", doctrine_models["Post"].fields)
            self.assertIn("author:?User", doctrine_models["Post"].fields)
            self.assertIn("tags:Collection", doctrine_models["Post"].fields)
            self.assertIn("table:symfony_demo_post", doctrine_models["Post"].annotations)
            self.assertIn("repository:PostRepository", doctrine_models["Post"].annotations)
            self.assertIn("primary-key:id", doctrine_models["Post"].annotations)
            self.assertIn("relation:author:ManyToOne", doctrine_models["Post"].annotations)
            self.assertIn("relation:tags:ManyToMany", doctrine_models["Post"].annotations)
            self.assertIn("join-table:tags:post_tag", doctrine_models["Post"].annotations)

            pages = {page.path for page in facts.pages}
            self.assertIn("templates/blog/index.html.twig", pages)
            self.assertNotIn("templates/blog/_form.html.twig", pages)
            self.assertNotIn("templates/base.html.twig", pages)


if __name__ == "__main__":
    unittest.main()
