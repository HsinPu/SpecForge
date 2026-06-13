from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round70FastApiOpenApiClientCalibrationTests(unittest.TestCase):
    def test_fastapi_router_prefix_and_openapi_ts_generated_client_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backend = root / "backend" / "app"
            routes = backend / "api" / "routes"
            core = backend / "core"
            routes.mkdir(parents=True)
            core.mkdir(parents=True)

            (backend / "main.py").write_text(
                """
from fastapi import FastAPI
from app.api.main import api_router
from app.core.config import settings

app = FastAPI(openapi_url=f"{settings.API_V1_STR}/openapi.json")
app.include_router(api_router, prefix=settings.API_V1_STR)
""".strip(),
                encoding="utf-8",
            )
            (backend / "api" / "main.py").write_text(
                """
from fastapi import APIRouter
from app.api.routes import items

api_router = APIRouter()
api_router.include_router(items.router)
""".strip(),
                encoding="utf-8",
            )
            (core / "config.py").write_text(
                """
class Settings:
    API_V1_STR: str = "/api/v1"

settings = Settings()
""".strip(),
                encoding="utf-8",
            )
            (routes / "items.py").write_text(
                """
from fastapi import APIRouter
from app.models import ItemPublic

router = APIRouter(prefix="/items", tags=["items"])

@router.get("/{id}", response_model=ItemPublic, status_code=200)
def read_item(id: int, expand: str | None = None):
    return ItemPublic()
""".strip(),
                encoding="utf-8",
            )
            (backend / "models.py").write_text(
                """
import uuid
from sqlmodel import Field, Relationship, SQLModel

class ItemBase(SQLModel):
    title: str = Field(min_length=1)

class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(foreign_key="user.id")
    owner: "User" | None = Relationship(back_populates="items")

class ItemPublic(ItemBase):
    id: uuid.UUID
""".strip(),
                encoding="utf-8",
            )

            client = root / "frontend" / "src" / "client"
            client.mkdir(parents=True)
            (root / "frontend" / "package.json").write_text(
                '{"dependencies":{"@vitejs/plugin-react":"latest","vite":"latest","react":"latest"}}\n',
                encoding="utf-8",
            )
            (client / "sdk.gen.ts").write_text(
                """
import { OpenAPI } from './core/OpenAPI';
import { request as __request } from './core/request';

export class ItemsService {
  public static readItem(data: { id: number }) {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/items/{id}',
      path: {
        'id': data.id,
      },
    });
  }
}
""".strip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes_seen = {(route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("GET", "/api/v1/items/{id}", "read_item"), routes_seen)
            self.assertNotIn(("GET", "/{id}", "read_item"), routes_seen)

            call = next(call for call in facts.api_calls if call.endpoint == "/api/v1/items/{id}")
            self.assertEqual("openapi-ts-client", call.client)
            self.assertEqual("GET /api/v1/items/{id}", call.matched_route)

            link = next(link for link in facts.api_links if link.endpoint == "/api/v1/items/{id}")
            self.assertEqual("/api/v1/items/{id}", link.matched_route)
            self.assertEqual("exact", link.match_type)
            self.assertEqual("high", link.confidence)

            contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "fastapi" and contract.path == "/api/v1/items/{id}"
            )
            self.assertIn("path:id:int", contract.request_hints)
            self.assertIn("query:expand:str | None", contract.request_hints)
            self.assertIn("response_model:ItemPublic", contract.response_hints)
            self.assertIn("200", contract.status_codes)

            models = {(model.name, model.kind): model for model in facts.data_models}
            self.assertIn(("ItemBase", "sqlmodel-model"), models)
            self.assertIn(("Item", "sqlmodel-table"), models)
            self.assertIn(("ItemPublic", "sqlmodel-model"), models)
            self.assertIn("id:uuid.UUID", models[("Item", "sqlmodel-table")].fields)
            self.assertIn("primary-key:id", models[("Item", "sqlmodel-table")].annotations)
            self.assertIn("relationship:owner:back_populates:items", models[("Item", "sqlmodel-table")].annotations)


if __name__ == "__main__":
    unittest.main()
