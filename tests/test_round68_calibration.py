from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round68TauriCalibrationTests(unittest.TestCase):
    def test_tauri_commands_invokes_and_plugin_commands_are_linked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "@tauri-apps/api": "^2.0.0",
    "react": "^19.0.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            app_src = root / "src"
            app_src.mkdir()
            (app_src / "App.tsx").write_text(
                """
import { invoke } from '@tauri-apps/api/core';

export async function greet(name: string) {
  // invoke('commented')
  return invoke('hello_user', { name });
}

export async function version() {
  return window.__TAURI__.core.invoke('plugin:app|version');
}

export async function saveBlob(id: number[]) {
  return invoke('save_blob', { id });
}

export async function scaleFactor() {
  return window.__TAURI__.core.invoke('plugin:window|scale_factor');
}

export async function setTitle(value: string) {
  return window.__TAURI__.core.invoke('plugin:window|set_title', { value });
}

export async function templatePlaceholder() {
  return invoke('plugin:{{ plugin_name }}|ping');
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            tauri_src = root / "src-tauri" / "src"
            tauri_src.mkdir(parents=True)
            (tauri_src / "lib.rs").write_text(
                r"""
const DOC_SAMPLE: &str = r#"
#[tauri::command]
fn fake_doc() {}
"#;

// #[tauri::command]
// fn commented() {}

#[tauri::command(rename = "hello_user")]
pub async fn greet(name: String) -> Result<String, String> {
    Ok(format!("Hello {name}"))
}

#[tauri::command]
pub fn save_blob(id: [u8; 16]) -> Result<(), String> {
    Ok(())
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            plugin = root / "crates" / "tauri" / "src" / "app"
            plugin.mkdir(parents=True)
            (plugin / "plugin.rs").write_text(
                """
use crate::{
  command,
  plugin::{Builder, TauriPlugin},
  AppHandle, Runtime,
};

#[command(root = "crate")]
pub fn version<R: Runtime>(app: AppHandle<R>) -> String {
  app.package_info().version.to_string()
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            window_plugin = root / "crates" / "tauri" / "src" / "window"
            window_plugin.mkdir(parents=True)
            (window_plugin / "plugin.rs").write_text(
                """
use crate::{
  command,
  plugin::{Builder, TauriPlugin},
  Runtime, Window,
};

macro_rules! getter {
  ($cmd: ident, $ret: ty) => {
    #[command(root = "crate")]
    pub async fn $cmd<R: Runtime>(window: Window<R>) -> crate::Result<$ret> {
      window.$cmd().map_err(Into::into)
    }
  };
}

macro_rules! setter {
  ($cmd: ident, $input: ty) => {
    #[command(root = "crate")]
    pub async fn $cmd<R: Runtime>(window: Window<R>, value: $input) -> crate::Result<()> {
      window.$cmd(value).map_err(Into::into)
    }
  };
}

getter!(scale_factor, f64);
setter!(set_title, &str);
// getter!(commented_macro, bool);
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.method, route.path, route.handler, route.framework, route.kind) for route in facts.api_routes}
            self.assertIn(("TAURI", "tauri#hello_user", "greet", "tauri", "tauri-command"), routes)
            self.assertIn(("TAURI", "tauri#save_blob", "save_blob", "tauri", "tauri-command"), routes)
            self.assertIn(
                ("TAURI", "tauri#plugin:app|version", "app::plugin::version", "tauri", "tauri-plugin-command"),
                routes,
            )
            self.assertIn(
                ("TAURI", "tauri#plugin:window|scale_factor", "window::plugin::scale_factor", "tauri", "tauri-plugin-macro-command"),
                routes,
            )
            self.assertIn(
                ("TAURI", "tauri#plugin:window|set_title", "window::plugin::set_title", "tauri", "tauri-plugin-macro-command"),
                routes,
            )
            self.assertNotIn(("TAURI", "tauri#fake_doc", "fake_doc", "tauri", "tauri-command"), routes)
            self.assertNotIn(("TAURI", "tauri#commented", "commented", "tauri", "tauri-command"), routes)

            greet_route = next(route for route in facts.api_routes if route.path == "tauri#hello_user")
            self.assertEqual(["name"], [param.name for param in greet_route.parameters])
            self.assertEqual("Result<String, String>", greet_route.response_type)
            blob_route = next(route for route in facts.api_routes if route.path == "tauri#save_blob")
            self.assertEqual(["id"], [param.name for param in blob_route.parameters])
            self.assertEqual("[u8; 16]", blob_route.parameters[0].type)
            self.assertEqual("Result<(), String>", blob_route.response_type)
            set_title_route = next(route for route in facts.api_routes if route.path == "tauri#plugin:window|set_title")
            self.assertEqual(["value"], [param.name for param in set_title_route.parameters])
            self.assertEqual("&str", set_title_route.parameters[0].type)

            calls = {(call.method, call.endpoint, call.client) for call in facts.api_calls}
            self.assertIn(("TAURI", "tauri#hello_user", "tauri-invoke"), calls)
            self.assertIn(("TAURI", "tauri#save_blob", "tauri-invoke"), calls)
            self.assertIn(("TAURI", "tauri#plugin:app|version", "tauri-invoke"), calls)
            self.assertIn(("TAURI", "tauri#plugin:window|scale_factor", "tauri-invoke"), calls)
            self.assertIn(("TAURI", "tauri#plugin:window|set_title", "tauri-invoke"), calls)
            self.assertNotIn(("TAURI", "tauri#commented", "tauri-invoke"), calls)
            self.assertNotIn(("TAURI", "tauri#plugin:{{ plugin_name }}|ping", "tauri-invoke"), calls)

            links = {(link.endpoint, link.matched_route, link.confidence) for link in facts.api_links}
            self.assertIn(("tauri#hello_user", "tauri#hello_user", "high"), links)
            self.assertIn(("tauri#save_blob", "tauri#save_blob", "high"), links)
            self.assertIn(("tauri#plugin:app|version", "tauri#plugin:app|version", "high"), links)
            self.assertIn(("tauri#plugin:window|scale_factor", "tauri#plugin:window|scale_factor", "high"), links)
            self.assertIn(("tauri#plugin:window|set_title", "tauri#plugin:window|set_title", "high"), links)


if __name__ == "__main__":
    unittest.main()
