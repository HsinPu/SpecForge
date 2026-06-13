from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round125FlaskSqlAlchemyCalibrationTests(unittest.TestCase):

    def test_flask_sqlalchemy_alias_models_and_marshmallow_schemas_are_data_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / "conduit" / "articles"
            app.mkdir(parents=True)
            (root / "requirements.txt").write_text("Flask\nFlask-SQLAlchemy\nmarshmallow\n", encoding="utf-8")
            (app / "models.py").write_text(
                """
from conduit.database import Model, SurrogatePK, db, Column, reference_col, relationship

class Article(SurrogatePK, Model):
    __tablename__ = 'article'
    id = db.Column(db.Integer, primary_key=True)
    slug = Column(db.Text, unique=True)
    title = Column(db.String(100), nullable=False)
    author_id = reference_col('userprofile', nullable=False)
    author = relationship('UserProfile')

    def display_title(self):
        if self.slug:
            return self.slug
        else:
            return self.title
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (app / "serializers.py").write_text(
                """
from marshmallow import Schema, fields

class ArticleSchema(Schema):
    slug = fields.Str()
    title = fields.Str()
    updatedAt = fields.DateTime(dump_only=True)
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            models = {(model.name, model.kind, model.path): model for model in facts.data_models}
            article = models[("Article", "sqlalchemy-model", "conduit/articles/models.py")]
            self.assertIn("id:Integer", article.fields)
            self.assertIn("slug:Text", article.fields)
            self.assertIn("title:String", article.fields)
            self.assertIn("author_id:reference:userprofile", article.fields)
            self.assertIn("author:relationship:UserProfile", article.fields)
            self.assertFalse(any(field.startswith("else:") for field in article.fields))
            self.assertIn("primary-key:id", article.annotations)
            self.assertIn("unique:slug", article.annotations)
            self.assertIn("required:title", article.annotations)

            schema = models[("ArticleSchema", "marshmallow-schema", "conduit/articles/serializers.py")]
            self.assertIn("slug:fields.Str", schema.fields)
            self.assertIn("title:fields.Str", schema.fields)
            self.assertIn("updatedAt:fields.DateTime", schema.fields)
            self.assertIn("dump-only:updatedAt", schema.annotations)


if __name__ == "__main__":
    unittest.main()
