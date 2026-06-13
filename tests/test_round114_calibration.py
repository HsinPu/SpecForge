from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round114MixAliasCalibrationTests(unittest.TestCase):
    def test_mix_aliases_are_exposed_as_project_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mix.exs").write_text(
                """
defmodule Demo.MixProject do
  use Mix.Project

  def project do
    [
      app: :demo,
      deps: deps(),
      aliases: aliases()
    ]
  end

  defp deps do
    [
      {:phoenix, "~> 1.7"},
      {:ecto_sql, "~> 3.11"},
      {:postgrex, ">= 0.0.0"}
    ]
  end

  defp aliases do
    [
      "ecto.setup": ["ecto.create", "ecto.migrate", "run priv/repo/seeds.exs"],
      "ecto.reset": ["ecto.drop", "ecto.setup"],
      test: ["ecto.create --quiet", "ecto.migrate", "test"]
    ]
  end
end
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            commands = {command.name: command for command in facts.commands}
            self.assertIn("mix ecto.setup", commands)
            self.assertIn("mix ecto.reset", commands)
            self.assertIn("mix test", commands)
            self.assertIn("alias-step:ecto.create", commands["mix ecto.setup"].options)
            self.assertIn("alias-step:run priv/repo/seeds.exs", commands["mix ecto.setup"].options)
            self.assertIn("alias-step:ecto.drop", commands["mix ecto.reset"].options)
            self.assertIn("alias-step:ecto.create --quiet", commands["mix test"].options)
            self.assertEqual(1, sum(1 for command in facts.commands if command.name == "mix test"))


if __name__ == "__main__":
    unittest.main()
