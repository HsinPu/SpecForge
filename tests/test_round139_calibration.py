from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.extractors.test_map import build_test_maps
from specforge.models import ApiRouteFact, ComponentFact, DataModelFact, Evidence, FileFact


class Round139MetabaseScaleTestMapCalibrationTests(unittest.TestCase):
    def test_test_map_uses_indexes_without_losing_route_component_or_model_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tests = root / "tests"
            tests.mkdir()
            (tests / "models").mkdir()
            (tests / "user_route_test.ts").write_text(
                'test("loads user", async () => { await fetch("/api/users/123"); });\n',
                encoding="utf-8",
            )
            (tests / "UserProfileCard.test.tsx").write_text(
                "import { UserProfileCard } from '../src/UserProfileCard';\n"
                "test('renders', () => render(<UserProfileCard />));\n",
                encoding="utf-8",
            )
            (tests / "config.unit.spec.ts").write_text(
                'const type = "dashboard"; const title = "Error"; const assetPath = "/assets/logo.png";\n',
                encoding="utf-8",
            )
            (tests / "models" / "UserAccount_test.py").write_text(
                "def test_user_account_model():\n    assert True\n",
                encoding="utf-8",
            )

            test_files = [
                _file_fact("tests/user_route_test.ts", "typescript", root),
                _file_fact("tests/UserProfileCard.test.tsx", "typescript", root),
                _file_fact("tests/config.unit.spec.ts", "typescript", root),
                _file_fact("tests/models/UserAccount_test.py", "python", root),
            ]
            routes = [
                ApiRouteFact(
                    method="GET",
                    path="/:type/",
                    handler="dynamicType",
                    framework="clojure-ring",
                    kind="ring-route",
                    evidence=Evidence(file="src/routes/root.clj", kind="route", line_start=1),
                ),
                *[
                    ApiRouteFact(
                        method="GET",
                        path=f"/api/noise{i}/{{id}}",
                        handler=f"Noise{i}Handler",
                        framework="express",
                        kind="express-route",
                        evidence=Evidence(file=f"src/routes/noise{i}.ts", kind="route", line_start=1),
                    )
                    for i in range(800)
                ],
                ApiRouteFact(
                    method="GET",
                    path="/api/users/{id}",
                    handler="getUser",
                    framework="express",
                    kind="express-route",
                    evidence=Evidence(file="src/routes/users.ts", kind="route", line_start=1),
                ),
            ]
            components = [
                *[
                    ComponentFact(
                        name=f"NoiseWidget{i}",
                        path=f"src/components/NoiseWidget{i}.tsx",
                        framework="react",
                        props=[],
                        hooks=[],
                        evidence=Evidence(file=f"src/components/NoiseWidget{i}.tsx", kind="component", line_start=1),
                    )
                    for i in range(1200)
                ],
                ComponentFact(
                    name="UserProfileCard",
                    path="src/components/UserProfileCard.tsx",
                    framework="react",
                    props=["user"],
                    hooks=[],
                    evidence=Evidence(file="src/components/UserProfileCard.tsx", kind="component", line_start=1),
                ),
            ]
            data_models = [
                *[
                    DataModelFact(
                        name=f"NoiseModel{i}",
                        path=f"src/models/NoiseModel{i}.py",
                        kind="python-dataclass",
                        fields=[],
                        annotations=[],
                        evidence=Evidence(file=f"src/models/NoiseModel{i}.py", kind="data-model", line_start=1),
                    )
                    for i in range(700)
                ],
                DataModelFact(
                    name="UserAccount",
                    path="src/models/UserAccount.py",
                    kind="python-dataclass",
                    fields=["id", "email"],
                    annotations=[],
                    evidence=Evidence(file="src/models/UserAccount.py", kind="data-model", line_start=1),
                ),
            ]

            maps = {
                item.test_path: item
                for item in build_test_maps(root, test_files, routes, components, [], [], [], data_models)
            }

            self.assertEqual("api-route", maps["tests/user_route_test.ts"].target_kind)
            self.assertEqual("GET /api/users/{id}", maps["tests/user_route_test.ts"].target)
            self.assertEqual("component", maps["tests/UserProfileCard.test.tsx"].target_kind)
            self.assertEqual("UserProfileCard", maps["tests/UserProfileCard.test.tsx"].target)
            self.assertEqual("unmatched", maps["tests/config.unit.spec.ts"].target_kind)
            self.assertEqual("data-model", maps["tests/models/UserAccount_test.py"].target_kind)
            self.assertEqual("UserAccount", maps["tests/models/UserAccount_test.py"].target)


def _file_fact(path: str, language: str, root: Path) -> FileFact:
    file_path = root / path
    return FileFact(
        path=path,
        language=language,
        role="test",
        size_bytes=file_path.stat().st_size,
        evidence=Evidence(file=path, kind="file", line_start=1),
    )


if __name__ == "__main__":
    unittest.main()
