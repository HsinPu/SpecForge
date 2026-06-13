from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round63ElectronCalibrationTests(unittest.TestCase):
    def test_electron_ipc_routes_calls_links_and_react_router(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "assets").mkdir()
            (root / "src" / "main").mkdir(parents=True)
            (root / "src" / "renderer").mkdir(parents=True)
            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "electron": "^31.0.0",
    "react": "^19.0.0",
    "react-router-dom": "^6.26.0"
  },
  "devDependencies": {
    "@electron/rebuild": "^3.6.0"
  }
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "assets" / "entitlements.mac.plist").write_text(
                """
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
  <dict>
    <key>com.apple.security.cs.allow-jit</key>
    <true/>
  </dict>
</plist>
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src" / "main" / "main.ts").write_text(
                """
import { app, BrowserWindow, ipcMain } from 'electron';

ipcMain.handle('settings:get', async () => ({ theme: 'dark' }));
ipcMain.on('ping', (event, payload) => {
  event.reply('pong', payload);
});
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src" / "main" / "preload.ts").write_text(
                """
import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electron', {
  ipcRenderer: {
    sendMessage(channel: string, payload?: unknown) {
      ipcRenderer.send(channel, payload);
    },
    invokeSettings() {
      return ipcRenderer.invoke('settings:get');
    },
  },
});
""".lstrip(),
                encoding="utf-8",
            )
            (root / "src" / "renderer" / "App.tsx").write_text(
                """
import { MemoryRouter as Router, Routes, Route } from 'react-router-dom';

function Home() {
  window.electron?.ipcRenderer.sendMessage('ping', ['hello']);
  window.electron?.ipcRenderer.once('settings:get', () => undefined);
  return <main>Home</main>;
}

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
      </Routes>
    </Router>
  );
}
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("electron", "desktop"), frameworks)
            self.assertIn(("react-router", "frontend"), frameworks)
            self.assertNotIn(("redwood", "frontend"), frameworks)
            self.assertNotIn(("ios", "mobile"), frameworks)

            frontend_routes = {(route.route, route.framework, route.kind) for route in facts.frontend_routes}
            self.assertIn(("/", "react", "react-router-route"), frontend_routes)
            self.assertFalse(any(route.framework == "redwood" for route in facts.frontend_routes))

            api_routes = {(route.method, route.path, route.framework, route.kind) for route in facts.api_routes}
            self.assertIn(("IPC", "ipc#settings:get", "electron", "electron-ipc-main"), api_routes)
            self.assertIn(("IPC", "ipc#ping", "electron", "electron-ipc-main"), api_routes)

            api_calls = {(call.method, call.endpoint, call.client, call.context) for call in facts.api_calls}
            self.assertIn(("IPC", "ipc#settings:get", "electron-ipc", "ipc-renderer:invoke"), api_calls)
            self.assertIn(("IPC", "ipc#ping", "electron-ipc", "ipc-renderer:sendMessage"), api_calls)

            api_links = {
                (link.method, link.endpoint, link.matched_route, link.matched_framework, link.match_type, link.confidence)
                for link in facts.api_links
            }
            self.assertIn(("IPC", "ipc#settings:get", "ipc#settings:get", "electron", "exact", "high"), api_links)
            self.assertIn(("IPC", "ipc#ping", "ipc#ping", "electron", "exact", "high"), api_links)


if __name__ == "__main__":
    unittest.main()
