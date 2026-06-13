from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round14CalibrationTests(unittest.TestCase):

    def test_scan_project_refines_rails_resources_and_doctrine_entities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config"
            config.mkdir()
            (config / "routes.rb").write_text(
                """
Rails.application.routes.draw do
  scope :api, defaults: { format: :json } do
    resources :articles, param: :slug, except: [:edit, :new] do
      resource :favorite, only: [:create, :destroy]
      resources :comments, only: [:create, :index, :destroy]
      get :feed, on: :collection
    end
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )
            entity = root / "src" / "Entity"
            entity.mkdir(parents=True)
            (entity / "Article.php").write_text(
                """
<?php

use Doctrine\\ORM\\Mapping as ORM;

/**
 * @ORM\\Entity(repositoryClass="App\\Repository\\ArticleRepository")
 * @ORM\\Table(name="rw_article")
 */
class Article
{
    /** @ORM\\Column(type="string") */
    private ?string $title = null;

    /** @ORM\\ManyToOne(targetEntity="App\\Entity\\User") */
    private ?User $author = null;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.framework, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("rails", "GET", "/api/articles", "articles#index"), routes)
            self.assertIn(("rails", "POST", "/api/articles", "articles#create"), routes)
            self.assertIn(("rails", "GET", "/api/articles/{slug}", "articles#show"), routes)
            self.assertIn(("rails", "PATCH", "/api/articles/{slug}", "articles#update"), routes)
            self.assertIn(("rails", "DELETE", "/api/articles/{slug}", "articles#destroy"), routes)
            self.assertIn(("rails", "POST", "/api/articles/{slug}/favorite", "favorite#create"), routes)
            self.assertIn(("rails", "DELETE", "/api/articles/{slug}/favorite", "favorite#destroy"), routes)
            self.assertIn(("rails", "GET", "/api/articles/{slug}/comments", "comments#index"), routes)
            self.assertIn(("rails", "POST", "/api/articles/{slug}/comments", "comments#create"), routes)
            self.assertIn(("rails", "DELETE", "/api/articles/{slug}/comments/{id}", "comments#destroy"), routes)
            self.assertIn(("rails", "GET", "/api/articles/feed", "articles#feed"), routes)

            doctrine = [item for item in facts.data_layers if item.kind == "doctrine-entity"]
            self.assertEqual(1, len(doctrine))
            self.assertIn("table:rw_article", doctrine[0].details)
            self.assertIn("column:title", doctrine[0].details)
            self.assertIn("relation:ManyToOne", doctrine[0].details)

    def test_scan_project_refines_rails_namespaces_module_scopes_and_collection_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config"
            config.mkdir()
            (config / "routes.rb").write_text(
                """
Rails.application.routes.draw do
  mount_devise_token_auth_for 'User', at: 'auth'

  namespace :api, defaults: { format: 'json' } do
    namespace :v1 do
      resources :accounts, only: [:show] do
        scope module: :accounts do
          namespace :actions do
            resource :contact_merge, only: [:create]
          end
          resources :agents, only: [:index, :create, :update, :destroy] do
            post :bulk_create, on: :collection
            collection do
              get :search
            end
            member do
              delete :avatar
            end
          end
        end
        scope module: 'profile' do
          resource :mfa, controller: 'mfa', only: [:show, :create, :destroy] do
            post :verify
          end
        end
      end
    end
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.framework, route.method, route.path) for route in facts.api_routes}
            self.assertIn(("rails", "POST", "/auth/sign_in"), routes)
            self.assertIn(("rails", "GET", "/api/v1/accounts/{id}"), routes)
            self.assertIn(("rails", "POST", "/api/v1/accounts/{id}/actions/contact_merge"), routes)
            self.assertIn(("rails", "GET", "/api/v1/accounts/{id}/agents"), routes)
            self.assertIn(("rails", "POST", "/api/v1/accounts/{id}/agents"), routes)
            self.assertIn(("rails", "PATCH", "/api/v1/accounts/{id}/agents/{id}"), routes)
            self.assertIn(("rails", "DELETE", "/api/v1/accounts/{id}/agents/{id}"), routes)
            self.assertIn(("rails", "POST", "/api/v1/accounts/{id}/agents/bulk_create"), routes)
            self.assertIn(("rails", "GET", "/api/v1/accounts/{id}/agents/search"), routes)
            self.assertIn(("rails", "DELETE", "/api/v1/accounts/{id}/agents/{id}/avatar"), routes)
            self.assertIn(("rails", "GET", "/api/v1/accounts/{id}/mfa"), routes)
            self.assertIn(("rails", "POST", "/api/v1/accounts/{id}/mfa"), routes)
            self.assertIn(("rails", "DELETE", "/api/v1/accounts/{id}/mfa"), routes)
            self.assertIn(("rails", "POST", "/api/v1/accounts/{id}/mfa/verify"), routes)
            self.assertFalse(any("/module/" in route.path for route in facts.api_routes))

    def test_scan_project_detects_symfony_annotations_and_aspnet_minimal_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symfony = root / "src" / "Controller" / "Article"
            symfony.mkdir(parents=True)
            (symfony / "CreateArticleController.php").write_text(
                """
<?php

use Symfony\\Component\\Routing\\Annotation\\Route;

/**
 * @Route("/api/articles", methods={"POST"}, name="api_articles_post")
 */
final class CreateArticleController
{
    public function __invoke(Request $request): array
    {
        return [];
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            endpoints = root / "src" / "Presentation" / "Endpoints"
            endpoints.mkdir(parents=True)
            (root / "Demo.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk.Web"></Project>\n', encoding="utf-8")
            (endpoints / "ReviewEndpoints.cs").write_text(
                """
public static class ReviewEndpoints
{
    public static WebApplication MapReviewEndpoints(this WebApplication app)
    {
        var root = app.MapGroup("/api/review")
            .WithTags("review");

        _ = root.MapGet("/", GetReviews);
        _ = root.MapGet("/{id}", GetReviewById);
        _ = root.MapPost("/", CreateReview);
        _ = root.MapDelete("/{id}", DeleteReview);
        return app;
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (endpoints / "TodoLists.cs").write_text(
                """
public class TodoLists : IEndpointGroup
{
    public static void Map(RouteGroupBuilder groupBuilder)
    {
        groupBuilder.MapGet(GetTodoLists);
        groupBuilder.MapPut(UpdateTodoList, "{id}");
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            angular = root / "src" / "Web" / "ClientApp" / "src" / "app"
            angular.mkdir(parents=True)
            (angular / "app.module.ts").write_text(
                """
import { NgModule } from '@angular/core';

@NgModule({})
export class AppModule {}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("angular", frameworks)
            self.assertIn("aspnetcore", frameworks)
            self.assertIn("symfony", frameworks)
            self.assertNotIn("nestjs", frameworks)

            routes = {(route.framework, route.kind, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("symfony", "symfony-annotation-route", "POST", "/api/articles", "__invoke"), routes)
            self.assertIn(("aspnetcore", "aspnetcore-minimal-route", "GET", "/api/review", "GetReviews"), routes)
            self.assertIn(("aspnetcore", "aspnetcore-minimal-route", "GET", "/api/review/{id}", "GetReviewById"), routes)
            self.assertIn(("aspnetcore", "aspnetcore-minimal-route", "POST", "/api/review", "CreateReview"), routes)
            self.assertIn(("aspnetcore", "aspnetcore-minimal-route", "DELETE", "/api/review/{id}", "DeleteReview"), routes)
            self.assertIn(("aspnetcore", "aspnetcore-minimal-route", "GET", "/api/TodoLists", "GetTodoLists"), routes)
            self.assertIn(("aspnetcore", "aspnetcore-minimal-route", "PUT", "/api/TodoLists/{id}", "UpdateTodoList"), routes)


if __name__ == "__main__":
    unittest.main()
