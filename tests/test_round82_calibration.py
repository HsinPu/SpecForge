from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round82AngularCalibrationTests(unittest.TestCase):
    def test_angular_entrypoint_config_tests_and_rxjs_state_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "scripts": {
    "start": "ng serve",
    "test": "ng test",
    "e2e": "ng e2e"
  },
  "dependencies": {
    "@angular/core": "^15.0.0",
    "@angular/router": "^15.0.0",
    "rxjs": "^7.0.0"
  },
  "devDependencies": {
    "@angular/cli": "^15.0.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "angular.json").write_text('{"projects":{"demo":{}}}\n', encoding="utf-8")
            src = root / "src"
            src.mkdir()
            (src / "main.ts").write_text(
                "import { platformBrowserDynamic } from '@angular/platform-browser-dynamic';\n",
                encoding="utf-8",
            )
            app = src / "app"
            app.mkdir()
            (app / "app-routing.module.ts").write_text(
                """
import { RouterModule, Routes } from '@angular/router';

const routes: Routes = [
  { path: 'dashboard', loadChildren: () => import('./dashboard/dashboard.module').then(m => m.DashboardModule) },
];

export const routing = RouterModule.forRoot(routes);
""".strip()
                + "\n",
                encoding="utf-8",
            )
            core = app / "core"
            core.mkdir()
            (core / "layout-state.service.ts").write_text(
                """
import { Injectable } from '@angular/core';
import { BehaviorSubject, Subject } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class LayoutStateService {
  private layoutState$ = new BehaviorSubject('default');
  private destroyed$ = new Subject<void>();

  setLayout(state: string) {
    this.layoutState$.next(state);
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            e2e = root / "e2e"
            e2e.mkdir()
            (e2e / "tsconfig.e2e.json").write_text('{"extends":"../tsconfig.json"}\n', encoding="utf-8")
            (e2e / ".eslintrc.json").write_text('{"root":true}\n', encoding="utf-8")
            (e2e / "app.e2e-spec.ts").write_text(
                """
describe('dashboard', () => {
  it('opens dashboard', () => {
    cy.visit('/dashboard');
  });
});
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            entrypoints = {(item.kind, item.path, item.command) for item in facts.entrypoints}
            self.assertIn(("angular-entrypoint", "src/main.ts", "npm run start"), entrypoints)

            files_by_path = {item.path: item for item in facts.files}
            self.assertEqual("test", files_by_path["e2e/tsconfig.e2e.json"].role)
            self.assertEqual("test", files_by_path["e2e/.eslintrc.json"].role)
            self.assertEqual("test", files_by_path["e2e/app.e2e-spec.ts"].role)
            self.assertEqual(
                {"e2e/.eslintrc.json", "e2e/app.e2e-spec.ts", "e2e/tsconfig.e2e.json"},
                {item.path for item in facts.test_files},
            )
            self.assertEqual(["e2e/app.e2e-spec.ts"], [item.test_path for item in facts.test_maps])

            state = {(item.library, item.usage, item.name) for item in facts.state_usages}
            self.assertIn(("angular-rxjs", "subject", "layoutState$"), state)
            self.assertIn(("angular-rxjs", "subject", "destroyed$"), state)
            self.assertIn(("angular-rxjs", "subject-next", "layoutState$"), state)


if __name__ == "__main__":
    unittest.main()
