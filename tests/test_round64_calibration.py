from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round64FlutterRouterinoCalibrationTests(unittest.TestCase):
    def test_routerino_dart_api_routes_and_strapi_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app" / "lib" / "provider").mkdir(parents=True)
            (root / "app" / "rust" / "src" / "api").mkdir(parents=True)
            (root / "common" / "lib").mkdir(parents=True)

            (root / "app" / "pubspec.yaml").write_text(
                """
name: demo_app
dependencies:
  flutter:
    sdk: flutter
  routerino: 0.8.0
  rhttp: 0.13.0
""".lstrip(),
                encoding="utf-8",
            )
            (root / "common" / "lib" / "api_route_builder.dart").write_text(
                """
const _basePath = '/api/localsend';

enum ApiRoute {
  info('info'),
  show('show'),
  prepareUpload('prepare-upload', 'send-request'),
  ;

  const ApiRoute(String path, [String? legacy])
      : v1 = '$_basePath/v1/${legacy ?? path}',
        v2 = '$_basePath/v2/$path';

  final String v1;
  final String v2;

  String targetRaw(String ip, int port, bool https, String version) {
    final protocol = https ? 'https' : 'http';
    final route = version == '1.0' ? v1 : v2;
    return '$protocol://$ip:$port$route';
  }
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "app" / "lib" / "main.dart").write_text(
                """
import 'package:flutter/material.dart';
import 'package:routerino/routerino.dart';

class HomePage extends StatelessWidget {
  const HomePage({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}

class ReceivePage extends StatelessWidget {
  const ReceivePage({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}

class ProgressPage extends StatelessWidget {
  const ProgressPage({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}

class NoFilesDialog extends StatelessWidget {
  const NoFilesDialog({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox();
}

Widget buildApp(BuildContext context) {
  context.push(() => const ReceivePage());
  context.pushBottomSheet(() => const NoFilesDialog());
  Routerino.context.pushAndRemoveUntil(
    removeUntil: HomePage,
    builder: () => const ProgressPage(),
  );
  return MaterialApp(
    navigatorKey: Routerino.navigatorKey,
    home: RouterinoHome(
      builder: () => const HomePage(),
    ),
  );
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "app" / "lib" / "provider" / "server_controller.dart").write_text(
                """
import 'dart:io';
import 'package:common/api_route_builder.dart';

class SimpleServerRouteBuilder {
  void get(String path, void Function(HttpRequest request) handler) {}
  void post(String path, void Function(HttpRequest request) handler) {}
}

void installRoutes(SimpleServerRouteBuilder router) {
  router.get(ApiRoute.info.v1, (HttpRequest request) async {
    return await _infoHandler(request);
  });
  router.post(ApiRoute.show.v1, (HttpRequest request) async {
    return await _showHandler(request);
  });
  router.post(ApiRoute.show.v2, (HttpRequest request) async {
    return await _showHandler(request);
  });
  router.get('/main.js', (HttpRequest request) async {});
}

Future<void> _infoHandler(HttpRequest request) async {}
Future<void> _showHandler(HttpRequest request) async {}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "app" / "lib" / "provider" / "client.dart").write_text(
                """
import 'package:common/api_route_builder.dart';

Future<void> ping(dynamic client, String version) async {
  await client.post(
    ApiRoute.show.targetRaw('127.0.0.1', 53317, false, version),
  );
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "app" / "rust" / "src" / "api" / "http.rs").write_text(
                """
use crate::api::stream;
pub use localsend::http::client::LsHttpClientVersion;
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("flutter", "frontend"), frameworks)
            self.assertIn(("routerino", "frontend"), frameworks)
            self.assertNotIn(("strapi", "backend"), frameworks)

            frontend_routes = {(route.route, route.framework, route.kind) for route in facts.frontend_routes}
            self.assertIn(("/", "flutter", "flutter-routerino-root"), frontend_routes)
            self.assertIn(("/ReceivePage", "flutter", "flutter-routerino-screen"), frontend_routes)
            self.assertIn(("/ProgressPage", "flutter", "flutter-routerino-screen"), frontend_routes)
            self.assertFalse(any(route.route == "/NoFilesDialog" for route in facts.frontend_routes))

            api_routes = {(route.method, route.path, route.framework, route.kind, route.handler) for route in facts.api_routes}
            self.assertIn(("GET", "/api/localsend/v1/info", "dart", "dart-simple-server-route", "_infoHandler"), api_routes)
            self.assertIn(("POST", "/api/localsend/v1/show", "dart", "dart-simple-server-route", "_showHandler"), api_routes)
            self.assertIn(("POST", "/api/localsend/v2/show", "dart", "dart-simple-server-route", "_showHandler"), api_routes)
            self.assertIn(("GET", "/main.js", "dart", "dart-simple-server-route", "inline-handler"), api_routes)

            api_calls = {(call.method, call.endpoint, call.client, call.context) for call in facts.api_calls}
            self.assertIn(("POST", "/api/localsend/v1/show", "client", "dart-api-route:targetRaw"), api_calls)
            self.assertIn(("POST", "/api/localsend/v2/show", "client", "dart-api-route:targetRaw"), api_calls)
            self.assertFalse(any(call.endpoint == "dynamic:ApiRoute" for call in facts.api_calls))

            links = {(link.method, link.endpoint, link.matched_route, link.matched_framework) for link in facts.api_links}
            self.assertIn(("POST", "/api/localsend/v1/show", "/api/localsend/v1/show", "dart"), links)
            self.assertIn(("POST", "/api/localsend/v2/show", "/api/localsend/v2/show", "dart"), links)


if __name__ == "__main__":
    unittest.main()
