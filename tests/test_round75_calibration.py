from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round75VendureCalibrationTests(unittest.TestCase):
    def test_workspace_package_scripts_bins_and_multiline_typeorm_entities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bun.lock").write_text("", encoding="utf-8")
            (root / "package.json").write_text(
                """
{
  "name": "vendure-like",
  "private": true,
  "workspaces": ["packages/*"],
  "scripts": {
    "build": "lerna run build",
    "test": "lerna run test"
  },
  "dependencies": {
    "@nestjs/core": "^10.0.0",
    "typeorm": "^0.3.0"
  }
}
""".strip(),
                encoding="utf-8",
            )

            cli = root / "packages" / "cli"
            cli.mkdir(parents=True)
            (cli / "package.json").write_text(
                """
{
  "name": "@demo/cli",
  "bin": {
    "vendure": "dist/cli.js"
  },
  "scripts": {
    "build": "tsc -p tsconfig.json",
    "test": "vitest run"
  }
}
""".strip(),
                encoding="utf-8",
            )

            entity_dir = root / "packages" / "core" / "src" / "entity" / "product"
            entity_dir.mkdir(parents=True)
            (entity_dir / "product.entity.ts").write_text(
                """
import { Column, Entity, JoinTable, ManyToMany, ManyToOne, OneToMany } from 'typeorm';
import { EntityId } from '../entity-id.decorator';

@Entity({ name: 'product' })
export class Product
    extends VendureEntity
    implements HasCustomFields, ChannelAware
{
    @Column({ type: Date, nullable: true })
    deletedAt: Date | null;

    name: string;

    @Column({ default: true })
    enabled: boolean;

    @ManyToOne(type => Asset, asset => asset.featuredInProducts, { onDelete: 'SET NULL' })
    featuredAsset: Asset;

    @EntityId({ nullable: true })
    featuredAssetId: ID;

    @OneToMany(type => ProductVariant, variant => variant.product)
    variants: ProductVariant[];

    @ManyToMany(type => Channel, channel => channel.products)
    @JoinTable()
    channels: Channel[];

    @Column(type => CustomProductFields)
    customFields: CustomProductFields;
}
""".strip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            entrypoints = {(entry.kind, entry.path, entry.command) for entry in facts.entrypoints}
            self.assertIn(("node-bin", "packages/cli/dist/cli.js", "vendure"), entrypoints)

            commands = {command.name: command for command in facts.commands}
            self.assertIn("bun run build", commands)
            self.assertIn("bun run test", commands)
            self.assertIn("bun --cwd packages/cli run build", commands)
            self.assertIn("bun --cwd packages/cli run test", commands)
            self.assertIn("script:lerna run build", commands["bun run build"].options)

            product = next(model for model in facts.data_models if model.name == "Product")
            self.assertEqual("nestjs-entity", product.kind)
            self.assertIn("deletedAt:Date | null", product.fields)
            self.assertIn("name:string", product.fields)
            self.assertIn("featuredAsset:Asset", product.fields)
            self.assertIn("channels:Channel[]", product.fields)
            self.assertIn("column:deletedAt", product.annotations)
            self.assertIn("nullable:deletedAt", product.annotations)
            self.assertIn("entity-id:featuredAssetId", product.annotations)
            self.assertIn("relation:ManyToOne:featuredAsset:Asset", product.annotations)
            self.assertIn("relation:OneToMany:variants:ProductVariant", product.annotations)
            self.assertIn("relation:ManyToMany:channels:Channel", product.annotations)
            self.assertIn("join-table:channels", product.annotations)
            self.assertIn("extends:VendureEntity", product.annotations)

            typeorm_product = next(
                item for item in facts.data_layers if item.kind == "typeorm-entity" and item.name == "Product"
            )
            self.assertIn("table:product", typeorm_product.details)
            self.assertIn("column:deletedAt", typeorm_product.details)
            self.assertIn("column:featuredAssetId", typeorm_product.details)
            self.assertIn("relation:ManyToOne:featuredAsset:Asset", typeorm_product.details)
            self.assertIn("relation:ManyToMany:channels:Channel", typeorm_product.details)

            code_model_product = next(
                item for item in facts.data_layers if item.kind == "code-model:nestjs-entity" and item.name == "Product"
            )
            self.assertIn("relation:OneToMany:variants:ProductVariant", code_model_product.details)


if __name__ == "__main__":
    unittest.main()
