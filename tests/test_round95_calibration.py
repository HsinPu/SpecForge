from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round95AngularCalibrationTests(unittest.TestCase):
    def test_angular_signals_and_rxjs_state_names_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "scripts": {
    "start": "ng serve",
    "test": "vitest"
  },
  "dependencies": {
    "@angular/core": "^18.0.0",
    "@angular/router": "^18.0.0",
    "rxjs": "^7.8.0"
  },
  "devDependencies": {
    "@angular/cli": "^18.0.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            src = root / "src" / "app"
            src.mkdir(parents=True)
            (src / "app.routes.ts").write_text(
                """
import { Routes } from '@angular/router';
import { HomeComponent } from './home.component';

export const routes: Routes = [
  { path: '', component: HomeComponent },
  { path: 'profile/:username', component: HomeComponent },
];
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (src / "home.component.ts").write_text(
                """
import { Component, computed, signal } from '@angular/core';

@Component({
  selector: 'app-home',
  template: '<button>{{ label() }}</button>',
  standalone: true
})
export class HomeComponent {
  isSubmitting = signal(false);
  label = computed(() => this.isSubmitting() ? 'Saving' : 'Save');
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (src / "user.service.ts").write_text(
                """
import { Injectable } from '@angular/core';
import { BehaviorSubject, Subject } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class UserService {
  private currentUserSubject = new BehaviorSubject<string | null>(null);
  private refreshSubject = new Subject<void>();
  public currentUser = this.currentUserSubject.asObservable();

  setUser(user: string): void {
    this.currentUserSubject.next(user);
    this.refreshSubject.next();
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            state = {(item.library, item.usage, item.name) for item in facts.state_usages}
            self.assertIn(("angular", "signal", "isSubmitting"), state)
            self.assertIn(("angular", "computed", "label"), state)
            self.assertIn(("angular-rxjs", "subject", "currentUserSubject"), state)
            self.assertIn(("angular-rxjs", "subject", "refreshSubject"), state)
            self.assertIn(("angular-rxjs", "observable", "currentUser<-currentUserSubject"), state)
            self.assertIn(("angular-rxjs", "subject-next", "currentUserSubject"), state)
            self.assertIn(("angular-rxjs", "subject-next", "refreshSubject"), state)


if __name__ == "__main__":
    unittest.main()
