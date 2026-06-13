from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round15CalibrationTests(unittest.TestCase):

    def test_scan_project_refines_mobile_preview_noise_and_desktop_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "@tauri-apps/api": "^2.0.0",
    "electron": "^31.0.0",
    "react": "^19.0.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "build.gradle.kts").write_text(
                """
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    composeOptions {}
}

dependencies {
    implementation("androidx.compose.ui:ui:1.7.0")
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            main_kotlin = root / "app" / "src" / "main" / "kotlin" / "demo"
            main_kotlin.mkdir(parents=True)
            (main_kotlin / "HomeScreen.kt").write_text(
                """
package demo

import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview

annotation class ThemePreviews

@Composable
fun HomeScreen(userName: String) {}

@Preview
@Composable
fun HomeScreenPreview() {}

@ThemePreviews
@Composable
fun HomeScreenPreviewDark() {}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            test_demo = root / "app" / "src" / "testDemo" / "kotlin" / "demo"
            test_demo.mkdir(parents=True)
            (test_demo / "PreviewNoise.kt").write_text(
                """
package demo

import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview

@Preview
@Composable
fun PreviewNoise() {}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            electron_main = root / "src" / "main"
            electron_main.mkdir(parents=True)
            (electron_main / "main.ts").write_text(
                """
import { app, BrowserWindow, ipcMain } from 'electron';
import path from 'path';

let mainWindow: BrowserWindow | null = null;
mainWindow = new BrowserWindow({
  webPreferences: {
    preload: path.join(__dirname, 'preload.js'),
  },
});
ipcMain.on('ipc-example', (_event, message) => console.log(message));
mainWindow.loadURL('http://localhost:1212');
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (electron_main / "preload.ts").write_text(
                """
import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electron', {
  send: (channel: string) => ipcRenderer.send('ipc-example', channel),
});
""".strip()
                + "\n",
                encoding="utf-8",
            )

            tauri = root / "src-tauri"
            tauri.mkdir()
            (tauri / "tauri.conf.json").write_text(
                """
{
  "productName": "tauri-app",
  "version": "0.1.0",
  "identifier": "com.example.demo",
  "build": {
    "frontendDist": "../dist",
    "devUrl": "http://localhost:1420"
  },
  "app": {
    "windows": [
      { "label": "main", "title": "Demo" }
    ]
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            tauri_src = tauri / "src"
            tauri_src.mkdir()
            (tauri_src / "lib.rs").write_text(
                """
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello {name}")
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![greet])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            roles = {file.path: file.role for file in facts.files}
            self.assertEqual("test", roles["app/src/testDemo/kotlin/demo/PreviewNoise.kt"])

            components = {component.name for component in facts.components}
            self.assertIn("HomeScreen", components)
            self.assertNotIn("HomeScreenPreview", components)
            self.assertNotIn("HomeScreenPreviewDark", components)
            self.assertNotIn("PreviewNoise", components)

            runtime_values = {
                value
                for runtime in facts.runtime_configs
                for value in runtime.values
            }
            self.assertIn("runtime:electron", runtime_values)
            self.assertIn("window:BrowserWindow", runtime_values)
            self.assertIn("preload:configured", runtime_values)
            self.assertIn("load:loadURL", runtime_values)
            self.assertIn("ipc-main:ipc-example", runtime_values)
            self.assertIn("ipc-renderer:ipc-example", runtime_values)
            self.assertIn("context-bridge:electron", runtime_values)
            self.assertIn("runtime:tauri", runtime_values)
            self.assertIn("product:tauri-app", runtime_values)
            self.assertIn("identifier:com.example.demo", runtime_values)
            self.assertIn("window:main", runtime_values)
            self.assertIn("command:greet", runtime_values)
            self.assertIn("plugin:tauri_plugin_shell", runtime_values)
            self.assertIn("invoke-handler:greet", runtime_values)


if __name__ == "__main__":
    unittest.main()
