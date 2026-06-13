from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round118NestjsCalibrationTests(unittest.TestCase):

    def test_nestjs_typeorm_injected_repositories_and_entity_file_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"@nestjs/common":"^10.0.0","@nestjs/typeorm":"^10.0.0","typeorm":"^0.3.0"}}\n',
                encoding="utf-8",
            )
            article = root / "src" / "article"
            article.mkdir(parents=True)
            (article / "comment.entity.ts").write_text(
                """
import { Entity, PrimaryGeneratedColumn, Column } from 'typeorm';

@Entity()
export class Comment {
  @PrimaryGeneratedColumn()
  id: number;

  @Column()
  body: string;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (article / "article.entity.ts").write_text(
                """
import { Entity, PrimaryGeneratedColumn } from 'typeorm';

@Entity()
export class ArticleEntity {
  @PrimaryGeneratedColumn()
  id: number;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (article / "article.service.ts").write_text(
                """
import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { ArticleEntity } from './article.entity';
import { Comment } from './comment.entity';

@Injectable()
export class ArticleService {
  constructor(
    @InjectRepository(ArticleEntity)
    private readonly articleRepository: Repository<ArticleEntity>,
    @InjectRepository(Comment)
    private readonly commentRepository: Repository<Comment>
  ) {}
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            models = {(model.name, model.kind) for model in facts.data_models}
            self.assertIn(("ArticleEntity", "nestjs-entity"), models)
            self.assertIn(("Comment", "nestjs-entity"), models)

            repositories = {(repository.name, repository.entity, repository.base_interface, repository.path) for repository in facts.repositories}
            self.assertIn(("ArticleRepository", "ArticleEntity", "Repository<ArticleEntity>", "src/article/article.service.ts"), repositories)
            self.assertIn(("CommentRepository", "Comment", "Repository<Comment>", "src/article/article.service.ts"), repositories)

            data_layers = {(item.kind, item.name) for item in facts.data_layers}
            self.assertIn(("repository", "ArticleRepository"), data_layers)
            self.assertIn(("repository", "CommentRepository"), data_layers)


if __name__ == "__main__":
    unittest.main()
