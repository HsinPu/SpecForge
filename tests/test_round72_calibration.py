from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round72LaravelBladeCalibrationTests(unittest.TestCase):
    def test_blade_pages_forms_and_partials_are_scanned_without_partial_page_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "composer.json").write_text(
                '{"require":{"laravel/framework":"^11.0"}}\n',
                encoding="utf-8",
            )
            models = root / "app" / "Models"
            factories = root / "database" / "factories" / "Models"
            views = root / "resources" / "views"
            models.mkdir(parents=True)
            factories.mkdir(parents=True)
            (views / "auth" / "parts").mkdir(parents=True)
            (views / "layouts").mkdir()

            (views / "auth" / "login.blade.php").write_text(
                """
@extends('layouts.simple')
@section('content')
<main>
  <h1>Login</h1>
  @include('auth.parts.login-form-standard')
</main>
@stop
""".strip(),
                encoding="utf-8",
            )
            (views / "auth" / "parts" / "login-form-standard.blade.php").write_text(
                """
<form action="{{ url("/login") }}" method="POST">
  @csrf
  <input type="email" name="email">
  <input type="password" name="password">
</form>
<form action="{{ url("/settings/users/{$user->id}") }}" method="POST">
  <input type="hidden" name="_method" value="PUT">
</form>
""".strip(),
                encoding="utf-8",
            )
            (views / "layouts" / "simple.blade.php").write_text(
                """
<!doctype html>
<html>
<head>
  <link rel="stylesheet" href="{{ versioned_asset('dist/styles.css') }}">
</head>
<body>@yield('content')</body>
</html>
""".strip(),
                encoding="utf-8",
            )
            (models / "Book.php").write_text(
                """
<?php

namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Model;
use Illuminate\\Database\\Eloquent\\Relations\\HasMany;

/**
 * @property int $id
 * @property string $name
 */
class Book extends Model
{
    protected $table = 'books';
    protected $fillable = ['name'];
    protected $casts = ['published_at' => 'datetime'];

    public function pages(): HasMany
    {
        return $this->hasMany(Page::class);
    }
}
""".strip(),
                encoding="utf-8",
            )
            (models / "BookQueryBuilder.php").write_text(
                """
<?php

namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Builder;

class BookQueryBuilder extends Builder
{
}
""".strip(),
                encoding="utf-8",
            )
            (factories / "BookFactory.php").write_text(
                """
<?php

namespace Database\\Factories\\Models;

use Illuminate\\Database\\Eloquent\\Factories\\Factory;

class BookFactory extends Factory
{
    protected $model = \\App\\Models\\Book::class;
}
""".strip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            file_facts = {file.path: file for file in facts.files}
            self.assertEqual("blade", file_facts["resources/views/auth/login.blade.php"].language)
            self.assertEqual("frontend-page", file_facts["resources/views/auth/login.blade.php"].role)

            pages = {(page.route, page.template_engine, page.path) for page in facts.pages}
            self.assertIn(("/auth/login", "blade", "resources/views/auth/login.blade.php"), pages)
            self.assertNotIn(("/auth/parts/login-form-standard", "blade", "resources/views/auth/parts/login-form-standard.blade.php"), pages)
            self.assertNotIn(("/layouts/simple", "blade", "resources/views/layouts/simple.blade.php"), pages)

            forms = {(form.source, form.method, form.action, tuple(form.fields)) for form in facts.forms}
            self.assertIn(
                (
                    "resources/views/auth/parts/login-form-standard.blade.php",
                    "POST",
                    "/login",
                    ("email", "password"),
                ),
                forms,
            )

            model = next(model for model in facts.data_models if model.name == "Book")
            self.assertEqual("eloquent-model", model.kind)
            self.assertNotIn("BookFactory", {model.name for model in facts.data_models})
            self.assertNotIn("BookQueryBuilder", {model.name for model in facts.data_models})
            self.assertIn("name:string", model.fields)
            self.assertIn("name:fillable", model.fields)
            self.assertIn("published_at:datetime", model.fields)
            self.assertIn("table:books", model.annotations)
            self.assertIn("relation:pages:hasMany:Page", model.annotations)
            self.assertIn(
                (
                    "resources/views/auth/parts/login-form-standard.blade.php",
                    "POST",
                    "/settings/users/{user.id}",
                    ("_method",),
                ),
                forms,
            )


if __name__ == "__main__":
    unittest.main()
