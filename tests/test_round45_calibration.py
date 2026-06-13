from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round45AdonisCalibrationTests(unittest.TestCase):
    def test_adonis_routes_contracts_lucid_models_and_migrations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"@adonisjs/core":"^5.9.0","@adonisjs/lucid":"^18.3.0"}}\n',
                encoding="utf-8",
            )
            routes_dir = root / "start"
            controllers = root / "app" / "Controllers" / "Http"
            models = root / "app" / "Models"
            migrations = root / "database" / "migrations"
            user_tests = root / "tests" / "e2e" / "users"
            functional_tests = root / "tests" / "functional"
            routes_dir.mkdir(parents=True)
            controllers.mkdir(parents=True)
            models.mkdir(parents=True)
            migrations.mkdir(parents=True)
            user_tests.mkdir(parents=True)
            functional_tests.mkdir(parents=True)
            (routes_dir / "routes.ts").write_text(
                """
import Route from '@ioc:Adonis/Core/Route'

Route.get('/', 'ArticlesController.index').as('articles.index')
Route.get('/articles/:slug', 'ArticlesController.show').as('articles.show')
Route.post('/articles', 'ArticlesController.create').as('articles.create')

Route.group(() => {
  Route.get('/users', 'UsersController.index')
  Route.resource('profiles', 'ProfilesController').apiOnly()
}).prefix('/api').middleware('auth')
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (controllers / "ArticlesController.ts").write_text(
                """
import type { HttpContextContract } from '@ioc:Adonis/Core/HttpContext'
import CreateArticleValidator from '../../Validators/CreateArticleValidator'

export default class ArticlesController {
  public async index({ view }: HttpContextContract) {
    return view.render('articles/index')
  }

  public async show({ request, view }: HttpContextContract) {
    const article = await Article.findByOrFail('slug', request.param('slug'))
    return view.render('articles/show', { article })
  }

  public async create({ request, response, auth }: HttpContextContract) {
    const values = await request.validate(CreateArticleValidator)
    const page = request.input('page', 1)
    await auth.user?.related('articles').create(values)
    return response.redirect().toRoute('articles.show', { page })
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (user_tests / "new.spec.ts").write_text(
                "test.group('users/new', () => {})\n",
                encoding="utf-8",
            )
            (functional_tests / "home.spec.ts").write_text(
                "test('home', async ({ client }) => { await client.get('/') })\n",
                encoding="utf-8",
            )
            (models / "Article.ts").write_text(
                """
import { BaseModel, BelongsTo, belongsTo, column } from '@ioc:Adonis/Lucid/Orm'
import User from './User'

export default class Article extends BaseModel {
  @column({ isPrimary: true })
  public id: number

  @column()
  public title: string

  @belongsTo(() => User)
  public user: BelongsTo<typeof User>
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (migrations / "001_articles.ts").write_text(
                """
import BaseSchema from '@ioc:Adonis/Lucid/Schema'

export default class extends BaseSchema {
  protected tableName = 'articles'

  public async up() {
    this.schema.createTable(this.tableName, (table) => {
      table.increments('id')
      table.integer('user_id').unsigned().references('users.id')
      table.string('title').notNullable()
    })
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("adonisjs", frameworks)
            self.assertIn("adonis-lucid", frameworks)

            routes = {(route.framework, route.kind, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("adonisjs", "adonis-route", "GET", "/", "ArticlesController.index"), routes)
            self.assertIn(("adonisjs", "adonis-route", "GET", "/articles/:slug", "ArticlesController.show"), routes)
            self.assertIn(("adonisjs", "adonis-route", "POST", "/articles", "ArticlesController.create"), routes)
            self.assertIn(("adonisjs", "adonis-route", "GET", "/api/users", "UsersController.index"), routes)
            self.assertIn(("adonisjs", "adonis-resource-route", "GET", "/api/profiles", "ProfilesController.index"), routes)
            self.assertIn(("adonisjs", "adonis-resource-route", "DELETE", "/api/profiles/:profile_id", "ProfilesController.destroy"), routes)

            show_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "adonisjs" and contract.method == "GET" and contract.path == "/articles/:slug"
            )
            self.assertIn("path:slug", show_contract.request_hints)
            self.assertIn("path:request.param.slug", show_contract.request_hints)
            self.assertIn("view:articles/show", show_contract.response_hints)

            create_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "adonisjs" and contract.method == "POST" and contract.path == "/articles"
            )
            self.assertIn("validate:CreateArticleValidator", create_contract.request_hints)
            self.assertIn("body:request.input.page", create_contract.request_hints)
            self.assertIn("auth:auth.user", create_contract.request_hints)
            self.assertIn("response:redirect", create_contract.response_hints)
            self.assertIn("redirect-route:articles.show", create_contract.response_hints)

            models_by_name = {model.name: model for model in facts.data_models}
            self.assertIn("Article", models_by_name)
            self.assertIn("id:number", models_by_name["Article"].fields)
            self.assertIn("primary-key:id", models_by_name["Article"].annotations)
            self.assertIn("relation:belongsTo:user:User", models_by_name["Article"].annotations)

            data_layers = {(item.kind, item.name) for item in facts.data_layers}
            self.assertIn(("code-model:adonis-lucid-model", "Article"), data_layers)
            self.assertIn(("adonis-migration", "001_articles"), data_layers)
            migration = next(item for item in facts.data_layers if item.kind == "adonis-migration")
            self.assertIn("table:articles", migration.details)
            self.assertIn("column:title:string", migration.details)
            self.assertIn("references:users.id", migration.details)

            test_targets = {item.test_path: item.target for item in facts.test_maps}
            self.assertEqual("GET /", test_targets["tests/functional/home.spec.ts"])
            self.assertNotEqual("GET /", test_targets["tests/e2e/users/new.spec.ts"])


if __name__ == "__main__":
    unittest.main()
