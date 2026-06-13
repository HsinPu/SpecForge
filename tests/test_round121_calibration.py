from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round121AngularRealworldCalibrationTests(unittest.TestCase):

    def test_angular_httpclient_concat_beats_generic_service_call_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = root / "src" / "app" / "features" / "profile" / "services"
            page = root / "src" / "app" / "features" / "article" / "pages" / "article"
            service.mkdir(parents=True)
            page.mkdir(parents=True)
            (root / "package.json").write_text(
                '{"dependencies":{"@angular/common":"^18.0.0","@angular/core":"^18.0.0","@angular/router":"^18.0.0"}}\n',
                encoding="utf-8",
            )
            (service / "profile.service.ts").write_text(
                """
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({ providedIn: 'root' })
export class ProfileService {
  constructor(private readonly http: HttpClient) {}

  get(username: string) {
    return this.http.get<{ profile: Profile }>('/profiles/' + username);
  }

  follow(username: string) {
    return this.http.post<{ profile: Profile }>('/profiles/' + username + '/follow', {});
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (page / "article.component.ts").write_text(
                """
import { Component } from '@angular/core';

@Component({ selector: 'app-article', template: '' })
export class ArticleComponent {
  load(slug: string) {
    this.articleService.get(slug);
    this.articleService.delete(this.route.snapshot.params['slug']);
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            api_calls = {(call.method, call.endpoint, call.client, call.context) for call in facts.api_calls}
            self.assertIn(("GET", "/profiles/:username", "angular-httpclient", "source"), api_calls)
            self.assertIn(("POST", "/profiles/:username/follow", "angular-httpclient", "source"), api_calls)
            self.assertNotIn(("GET", "/profiles/", "http", "source"), api_calls)
            self.assertFalse(any(call.endpoint in {"dynamic:slug", "dynamic:this"} for call in facts.api_calls))


if __name__ == "__main__":
    unittest.main()
