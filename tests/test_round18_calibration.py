from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round18CalibrationTests(unittest.TestCase):

    def test_scan_project_detects_ml_and_mlops_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            (root / "requirements.txt").write_text(
                "\n".join(
                    [
                        "torch",
                        "pytorch-lightning",
                        "tensorflow",
                        "keras",
                        "scikit-learn",
                        "transformers",
                        "mlflow",
                        "dvc[s3]",
                        "hydra-core",
                        "wandb",
                        "streamlit",
                        "gradio",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "dvc.yaml").write_text(
                """
stages:
  train:
    cmd: python src/train.py
    deps:
      - data/train.csv
      - src/train.py
    params:
      - train.epochs
    metrics:
      - metrics.json
    outs:
      - models/model.pt
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "MLproject").write_text(
                """
name: fraud-model
entry_points:
  main:
    parameters:
      epochs: {type: int, default: 5}
    command: "python src/train.py --epochs {epochs}"
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "params.yaml").write_text(
                """
train:
  epochs: 5
model:
  hidden_size: 32
""".strip()
                + "\n",
                encoding="utf-8",
            )
            conf = root / "conf"
            conf.mkdir()
            (conf / "config.yaml").write_text(
                """
defaults:
  - model: small
hydra:
  run:
    dir: outputs/${now:%Y-%m-%d}
trainer:
  _target_: lightning.pytorch.Trainer
""".strip()
                + "\n",
                encoding="utf-8",
            )
            configs = root / "configs"
            configs.mkdir()
            (configs / "train.yaml").write_text(
                """
defaults:
  - model: small
task_name: train
""".strip()
                + "\n",
                encoding="utf-8",
            )
            streamlit_dir = root / ".streamlit"
            streamlit_dir.mkdir()
            (streamlit_dir / "config.toml").write_text(
                """
[server]
port = 8501
""".strip()
                + "\n",
                encoding="utf-8",
            )

            src = root / "src"
            src.mkdir()
            (src / "train.py").write_text(
                """
import hydra
import mlflow
import torch
import wandb
from lightning.pytorch import LightningModule
from sklearn.ensemble import RandomForestClassifier
from torch import nn
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer


class FraudDataset(Dataset):
    pass


class FraudModel(nn.Module):
    pass


class FraudLightningModule(LightningModule):
    pass


@hydra.main(version_base=None, config_path="../conf", config_name="config")
def train(cfg):
    loader = DataLoader(FraudDataset())
    model = RandomForestClassifier()
    tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
    backbone = AutoModel.from_pretrained("bert-base-uncased")
    mlflow.start_run()
    mlflow.log_metric("loss", 0.1)
    wandb.init(project="fraud")
    wandb.log({"loss": 0.1})
    torch.save({"model": model}, "models/model.pt")
    return loader, tokenizer, backbone
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (src / "app.py").write_text(
                """
import streamlit as st

st.title("Fraud model")
st.write("Ready")
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (src / "gradio_app.py").write_text(
                """
import gradio as gr

demo = gr.Interface(fn=lambda text: text, inputs="text", outputs="text")
demo.launch()
""".strip()
                + "\n",
                encoding="utf-8",
            )
            notebook = {
                "cells": [
                    {
                        "cell_type": "code",
                        "source": [
                            "import tensorflow as tf\n",
                            "from keras.models import Sequential\n",
                            "model = tf.keras.Sequential([])\n",
                            "model.save('model.keras')\n",
                        ],
                    }
                ],
                "metadata": {"kernelspec": {"name": "python3", "language": "python"}},
            }
            (root / "notebooks").mkdir()
            (root / "notebooks" / "tensorflow.ipynb").write_text(json.dumps(notebook), encoding="utf-8")

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertTrue(
                {
                    "dvc",
                    "gradio",
                    "hydra",
                    "keras",
                    "mlflow",
                    "pytorch",
                    "pytorch-lightning",
                    "scikit-learn",
                    "streamlit",
                    "tensorflow",
                    "transformers",
                    "wandb",
                }
                <= frameworks
            )

            data_kinds = {fact.kind for fact in facts.data_layers}
            self.assertTrue({"ml-pipeline", "notebook"} <= data_kinds)
            data_details = {detail for fact in facts.data_layers for detail in fact.details}
            self.assertIn("model-class:FraudModel", data_details)
            self.assertIn("dataset-class:FraudDataset", data_details)
            self.assertIn("train-function:train", data_details)
            self.assertIn("framework:tensorflow", data_details)
            self.assertIn("framework:gradio", data_details)

            runtime_kinds = {fact.kind for fact in facts.runtime_configs}
            self.assertTrue(
                {
                    "dvc-pipeline",
                    "hydra-config",
                    "ml-app",
                    "ml-params",
                    "ml-source",
                    "mlproject",
                    "notebook",
                    "streamlit-config",
                }
                <= runtime_kinds
            )
            runtime_values = {value for fact in facts.runtime_configs for value in fact.values}
            self.assertIn("stage:train", runtime_values)
            self.assertIn("entry-point:main", runtime_values)
            self.assertIn("framework:pytorch", runtime_values)
            self.assertIn("framework:streamlit", runtime_values)
            self.assertIn("framework:gradio", runtime_values)
            self.assertIn("tracking:mlflow", runtime_values)
            self.assertIn("tracking:wandb", runtime_values)


if __name__ == "__main__":
    unittest.main()
