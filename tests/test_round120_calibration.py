from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round120FastApiCalibrationTests(unittest.TestCase):

    def test_fastapi_route_facts_include_signature_body_and_response_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / "app" / "api" / "routes"
            app.mkdir(parents=True)
            (root / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi", "sqlmodel"]\n', encoding="utf-8")
            (app / "items.py").write_text(
                """
import uuid
from typing import Annotated, Any
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr

class ItemCreate: ...
class ItemPublic: ...
class Message: ...

router = APIRouter(prefix="/items")

@router.get("/{id}", response_model=ItemPublic)
def read_item(session = Depends(), id: uuid.UUID = None, expand: str | None = None) -> Any:
    return ItemPublic()

@router.post("/", response_model=ItemPublic)
def create_item(*, session = Depends(), item_in: ItemCreate) -> Any:
    return item_in

@router.post("/login", response_model=Message)
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Message:
    return Message()

@router.post("/test-email", response_model=Message)
def test_email(email_to: EmailStr) -> Message:
    return Message()

@router.delete("/{id}")
def delete_item(id: uuid.UUID) -> Message:
    return Message()
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            read_item = next(route for route in facts.api_routes if route.method == "GET" and route.path == "/items/{id}")
            self.assertEqual("ItemPublic", read_item.response_type)
            self.assertEqual(
                [("id", "path", "uuid.UUID", True), ("expand", "query", "str | None", False)],
                [(param.name, param.source, param.type, param.required) for param in read_item.parameters],
            )

            create_item = next(route for route in facts.api_routes if route.method == "POST" and route.path == "/items")
            self.assertEqual("ItemCreate", create_item.request_body)
            self.assertEqual("ItemPublic", create_item.response_type)
            self.assertEqual([("item_in", "body", "ItemCreate", True)], [(param.name, param.source, param.type, param.required) for param in create_item.parameters])

            login = next(route for route in facts.api_routes if route.method == "POST" and route.path == "/items/login")
            self.assertIsNone(login.request_body)
            self.assertEqual([], login.parameters)

            test_email = next(route for route in facts.api_routes if route.method == "POST" and route.path == "/items/test-email")
            self.assertIsNone(test_email.request_body)
            self.assertEqual([("email_to", "query", "EmailStr", None)], [(param.name, param.source, param.type, param.required) for param in test_email.parameters])

            delete_item = next(route for route in facts.api_routes if route.method == "DELETE" and route.path == "/items/{id}")
            self.assertEqual("Message", delete_item.response_type)
            self.assertEqual([("id", "path", "uuid.UUID", True)], [(param.name, param.source, param.type, param.required) for param in delete_item.parameters])


if __name__ == "__main__":
    unittest.main()
