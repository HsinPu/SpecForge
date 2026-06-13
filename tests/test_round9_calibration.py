from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round9CalibrationTests(unittest.TestCase):

    def test_scan_project_detects_typeorm_and_avoids_flask_settings_django_false_positive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "@nestjs/common": "^10.0.0",
    "@nestjs/typeorm": "^10.0.0",
    "typeorm": "^0.3.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            src = root / "src"
            src.mkdir()
            (src / "app.module.ts").write_text(
                """
import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { UserEntity } from './user.entity';

@Module({
  imports: [TypeOrmModule.forRoot(), TypeOrmModule.forFeature([UserEntity])],
})
export class AppModule {}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (src / "user.entity.ts").write_text(
                """
import { Entity, PrimaryGeneratedColumn, Column, OneToMany } from 'typeorm';

@Entity('users')
export class UserEntity {
  @PrimaryGeneratedColumn()
  id: number;

  @Column()
  email: string;

  @OneToMany(type => ArticleEntity, article => article.author)
  articles: ArticleEntity[];
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            (root / "requirements.txt").write_text("Flask==3.0.0\n", encoding="utf-8")
            flask_app = root / "conduit"
            flask_app.mkdir()
            (flask_app / "settings.py").write_text(
                """
import os

class Config(object):
    SECRET_KEY = os.environ.get("CONDUIT_SECRET", "secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite://")
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("nestjs", frameworks)
            self.assertIn("flask", frameworks)
            self.assertNotIn("django", frameworks)

            data_layers = {(item.kind, item.name) for item in facts.data_layers}
            self.assertIn(("typeorm-entity", "UserEntity"), data_layers)
            self.assertIn(("typeorm-module", "app.module"), data_layers)


if __name__ == "__main__":
    unittest.main()
