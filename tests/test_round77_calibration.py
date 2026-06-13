from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round77DrupalCalibrationTests(unittest.TestCase):
    def test_drupal_entities_config_schema_services_libraries_and_install_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "composer.json").write_text('{"require":{"drupal/core":"^11.0"}}\n', encoding="utf-8")
            module = root / "core" / "modules" / "demo"
            entity_dir = module / "src" / "Entity"
            entity_dir.mkdir(parents=True)
            (module / "config" / "schema").mkdir(parents=True)

            (entity_dir / "Article.php").write_text(
                """
<?php
namespace Drupal\\demo\\Entity;

use Drupal\\Core\\Entity\\Attribute\\ContentEntityType;
use Drupal\\Core\\Entity\\ContentEntityBase;
use Drupal\\Core\\Field\\BaseFieldDefinition;

#[ContentEntityType(
  id: 'demo_article',
  label: 'Demo article',
  entity_keys: [
    'id' => 'id',
    'label' => 'title',
  ],
  handlers: [
    'storage' => DemoArticleStorage::class,
    'form' => [
      'default' => DemoArticleForm::class,
    ],
  ],
  links: [
    'canonical' => '/demo/article/{demo_article}',
  ],
  base_table: 'demo_article',
  data_table: 'demo_article_field_data',
  admin_permission: 'administer demo articles',
)]
class Article extends ContentEntityBase {
  public static function baseFieldDefinitions($entity_type) {
    $fields = parent::baseFieldDefinitions($entity_type);
    $fields['title'] = BaseFieldDefinition::create('string');
    $fields['body'] = BaseFieldDefinition::create('text_long');
    return $fields;
  }
}
""".strip(),
                encoding="utf-8",
            )
            (entity_dir / "ArticleType.php").write_text(
                """
<?php
namespace Drupal\\demo\\Entity;

use Drupal\\Core\\Entity\\Attribute\\ConfigEntityType;
use Drupal\\Core\\Config\\Entity\\ConfigEntityBase;

#[ConfigEntityType(
  id: 'demo_article_type',
  label: 'Demo article type',
  entity_keys: [
    'id' => 'id',
  ],
  config_export: [
    'id',
    'label',
    'description',
  ],
)]
class ArticleType extends ConfigEntityBase {
  /**
   * @var string
   */
  protected $id;
  /**
   * @var string
   */
  protected $label;
  protected $description = '';
}
""".strip(),
                encoding="utf-8",
            )
            (module / "config" / "schema" / "demo.schema.yml").write_text(
                """
demo.article_type.*:
  type: config_entity
  label: 'Demo article type'
  mapping:
    id:
      type: machine_name
    label:
      type: label
    description:
      type: text
""".strip(),
                encoding="utf-8",
            )
            (module / "demo.services.yml").write_text(
                """
services:
  demo.article_manager:
    class: Drupal\\demo\\ArticleManager
    tags:
      - { name: event_subscriber }
""".strip(),
                encoding="utf-8",
            )
            (module / "demo.libraries.yml").write_text(
                """
article.admin:
  css:
    theme:
      css/article.css: {}
  js:
    js/article.js: {}
  dependencies:
    - core/drupal
""".strip(),
                encoding="utf-8",
            )
            (module / "demo.install").write_text(
                """
<?php
function demo_schema() {
  $schema['demo_log'] = [
    'description' => 'Demo log.',
  ];
  return $schema;
}
""".strip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            models = {model.name: model for model in facts.data_models}
            self.assertEqual("drupal-content-entity", models["Article"].kind)
            self.assertIn("title:string", models["Article"].fields)
            self.assertIn("body:text_long", models["Article"].fields)
            self.assertIn("entity-id:demo_article", models["Article"].annotations)
            self.assertIn("base-table:demo_article", models["Article"].annotations)
            self.assertIn("entity-key:id:id", models["Article"].annotations)
            self.assertIn("link:canonical:/demo/article/{demo_article}", models["Article"].annotations)

            self.assertEqual("drupal-config-entity", models["ArticleType"].kind)
            self.assertIn("label:config", models["ArticleType"].fields)
            self.assertIn("description:string", models["ArticleType"].fields)
            self.assertIn("config-export:description", models["ArticleType"].annotations)

            layers = {(item.kind, item.name): item for item in facts.data_layers}
            schema = layers[("drupal-config-schema", "demo.schema.yml")]
            self.assertIn("schema:demo.article_type.*", schema.details)
            self.assertIn("field:demo.article_type.*:description", schema.details)

            services = layers[("drupal-service-container", "demo.services.yml")]
            self.assertIn("service:demo.article_manager", services.details)
            self.assertIn("class:demo.article_manager:Drupal\\demo\\ArticleManager", services.details)
            self.assertIn("tag:demo.article_manager:event_subscriber", services.details)

            library = layers[("drupal-library", "demo.libraries.yml")]
            self.assertIn("library:article.admin", library.details)
            self.assertIn("asset:article.admin:css/article.css", library.details)
            self.assertIn("asset:article.admin:js/article.js", library.details)
            self.assertIn("dependency:article.admin:core/drupal", library.details)

            install = layers[("drupal-php-data", "demo")]
            self.assertIn("hook-schema:demo_schema", install.details)
            self.assertIn("table:demo_log", install.details)

            model_layer = layers[("code-model:drupal-content-entity", "Article")]
            self.assertIn("base-table:demo_article", model_layer.details)


if __name__ == "__main__":
    unittest.main()
