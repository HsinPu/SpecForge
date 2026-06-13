from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round50NestPrismaCalibrationTests(unittest.TestCase):
    def test_nestjs_routes_dtos_entities_and_prisma_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"@nestjs/common":"^8.0.0","@nestjs/swagger":"^5.0.0","@prisma/client":"^4.0.0"},"devDependencies":{"prisma":"^4.0.0"}}\n',
                encoding="utf-8",
            )
            articles = root / "src" / "articles"
            (articles / "dto").mkdir(parents=True)
            (articles / "entities").mkdir(parents=True)
            (root / "prisma").mkdir()
            (articles / "articles.controller.ts").write_text(
                """
import { Body, Controller, Delete, Get, Param, ParseIntPipe, Patch, Post } from '@nestjs/common';
import { ApiCreatedResponse, ApiOkResponse, ApiTags } from '@nestjs/swagger';
import { CreateArticleDto } from './dto/create-article.dto';
import { UpdateArticleDto } from './dto/update-article.dto';
import { ArticleEntity } from './entities/article.entity';
import { ArticlesService } from './articles.service';

@Controller('articles')
@ApiTags('articles')
export class ArticlesController {
  constructor(private readonly articlesService: ArticlesService) {}

  @Post()
  @ApiCreatedResponse({ type: ArticleEntity })
  create(@Body() createArticleDto: CreateArticleDto) {
    return this.articlesService.create(createArticleDto);
  }

  @Get(':id')
  @ApiOkResponse({ type: ArticleEntity })
  findOne(@Param('id', ParseIntPipe) id: number) {
    return this.articlesService.findOne(id);
  }

  @Patch(':id')
  @ApiCreatedResponse({ type: ArticleEntity })
  update(@Param('id', ParseIntPipe) id: number, @Body() updateArticleDto: UpdateArticleDto) {
    return this.articlesService.update(id, updateArticleDto);
  }

  @Delete(':id')
  @ApiOkResponse({ type: ArticleEntity })
  remove(@Param('id', ParseIntPipe) id: number) {
    return this.articlesService.remove(id);
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (articles / "dto" / "create-article.dto.ts").write_text(
                """
import { ApiProperty } from '@nestjs/swagger';
import { IsBoolean, IsNotEmpty, IsOptional, IsString, MaxLength, MinLength } from 'class-validator';

export class CreateArticleDto {
  @IsString()
  @IsNotEmpty()
  @MinLength(5)
  @ApiProperty()
  title: string;

  @IsString()
  @IsOptional()
  @IsNotEmpty()
  @MaxLength(300)
  @ApiProperty({ required: false })
  description?: string;

  @IsBoolean()
  @IsOptional()
  @ApiProperty({ required: false, default: false })
  published?: boolean = false;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (articles / "dto" / "update-article.dto.ts").write_text(
                """
import { PartialType } from '@nestjs/swagger';
import { CreateArticleDto } from './create-article.dto';

export class UpdateArticleDto extends PartialType(CreateArticleDto) {}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (articles / "entities" / "article.entity.ts").write_text(
                """
import { Article } from '@prisma/client';
import { ApiProperty } from '@nestjs/swagger';

export class ArticleEntity implements Article {
  @ApiProperty()
  id: number;

  @ApiProperty()
  title: string;

  @ApiProperty({ required: false, nullable: true })
  description: string | null;

  @ApiProperty()
  published: boolean;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "prisma" / "schema.prisma").write_text(
                """
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url = env("DATABASE_URL")
}

model Article {
  id          Int      @id @default(autoincrement())
  title       String   @unique
  description String?
  published   Boolean  @default(false)
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("nestjs", "backend"), frameworks)
            self.assertIn(("prisma", "data"), frameworks)

            routes = {(route.framework, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("nestjs", "POST", "/articles", "create"), routes)
            self.assertIn(("nestjs", "GET", "/articles/:id", "findOne"), routes)
            self.assertIn(("nestjs", "PATCH", "/articles/:id", "update"), routes)

            create_route = next(route for route in facts.api_routes if route.framework == "nestjs" and route.method == "POST")
            self.assertEqual("CreateArticleDto", create_route.request_body)
            self.assertEqual("ArticleEntity", create_route.response_type)

            update_route = next(route for route in facts.api_routes if route.framework == "nestjs" and route.method == "PATCH")
            self.assertEqual("UpdateArticleDto", update_route.request_body)
            self.assertIn(("path", "id", "number"), {(param.source, param.name, param.type) for param in update_route.parameters})

            update_contract = next(contract for contract in facts.api_contracts if contract.framework == "nestjs" and contract.method == "PATCH")
            self.assertIn("path:id:number", update_contract.request_hints)
            self.assertIn("body:UpdateArticleDto", update_contract.request_hints)
            self.assertIn("return:ArticleEntity", update_contract.response_hints)
            self.assertIn("201", update_contract.status_codes)

            models = {model.name: model for model in facts.data_models}
            self.assertEqual("prisma-model", models["Article"].kind)
            self.assertIn("id:Int", models["Article"].fields)
            self.assertIn("primary-key:id", models["Article"].annotations)
            self.assertEqual("nestjs-dto", models["CreateArticleDto"].kind)
            self.assertIn("title:string", models["CreateArticleDto"].fields)
            self.assertIn("required:title", models["CreateArticleDto"].annotations)
            self.assertIn("optional:description", models["CreateArticleDto"].annotations)
            self.assertNotIn("required:description", models["CreateArticleDto"].annotations)
            self.assertIn("partial-of:CreateArticleDto", models["UpdateArticleDto"].annotations)
            self.assertEqual("nestjs-entity", models["ArticleEntity"].kind)
            self.assertIn("implements:Article", models["ArticleEntity"].annotations)

            data_layers = {(layer.kind, layer.name) for layer in facts.data_layers}
            self.assertIn(("code-model:prisma-model", "Article"), data_layers)
            self.assertIn(("code-model:nestjs-dto", "CreateArticleDto"), data_layers)
            self.assertIn(("code-model:nestjs-entity", "ArticleEntity"), data_layers)


if __name__ == "__main__":
    unittest.main()
