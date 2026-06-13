from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round54FlutterCalibrationTests(unittest.TestCase):
    def test_flutter_routes_state_api_calls_and_freezed_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lib" / "services" / "api").mkdir(parents=True)
            (root / "lib" / "features" / "products" / "models").mkdir(parents=True)
            (root / "lib" / "features" / "products" / "screens").mkdir(parents=True)
            (root / "lib" / "features" / "products" / "providers").mkdir(parents=True)
            (root / "pubspec.yaml").write_text(
                """
name: flutter_fixture
dependencies:
  flutter:
    sdk: flutter
  go_router: ^14.0.0
  hooks_riverpod: ^2.0.0
  flutter_hooks: ^0.20.0
  dio: ^5.0.0
  freezed_annotation: ^2.0.0
""".lstrip(),
                encoding="utf-8",
            )
            (root / "lib" / "main.dart").write_text(
                """
import 'package:flutter/material.dart';
import 'package:hooks_riverpod/hooks_riverpod.dart';

void main() {
  runApp(const ProviderScope(child: DummyMartApp()));
}

class DummyMartApp extends HookConsumerWidget {
  const DummyMartApp({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    return MaterialApp.router(routerConfig: router);
  }
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "lib" / "services" / "router.dart").write_text(
                """
import 'package:go_router/go_router.dart';
import 'package:hooks_riverpod/hooks_riverpod.dart';

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(routes: [
    GoRoute(path: '/products', routes: [
      GoRoute(path: ':id'),
    ]),
    NavigationItem(path: '/posts', routes: [
      GoRoute(path: ':id'),
    ]),
    GoRoute(path: '/todos', routes: [
      GoRoute(path: 'add'),
      GoRoute(path: ':id', routes: [
        GoRoute(path: 'update'),
      ]),
    ]),
    GoRoute(path: '/login'),
  ]);
});
""".lstrip(),
                encoding="utf-8",
            )
            (root / "lib" / "features" / "products" / "providers" / "products.dart").write_text(
                """
import 'package:riverpod_annotation/riverpod_annotation.dart';

@riverpod
Future<List<Product>> products(ProductsRef ref) async {
  return [];
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "lib" / "features" / "products" / "screens" / "products.dart").write_text(
                """
import 'package:flutter/widgets.dart';
import 'package:flutter_hooks/flutter_hooks.dart';
import 'package:hooks_riverpod/hooks_riverpod.dart';

class ProductsScreen extends HookConsumerWidget {
  const ProductsScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final products = ref.watch(productsProvider);
    final query = useState('');
    ref.refresh(productsProvider);
    return Text(query.value + products.toString());
  }
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "lib" / "services" / "api" / "api_client.dart").write_text(
                """
import 'package:dio/dio.dart';

class ApiClient {
  final _httpClient = Dio(BaseOptions(baseUrl: 'https://dummyjson.com'));

  Future<Response> getProduct(int id) {
    return _httpClient.get('/products/$id');
  }

  Future<Response> addTodo(Map<String, dynamic> body) {
    return _httpClient.post('/todos/add', data: body);
  }

  Future<Response> listPosts() {
    final path = '/posts';
    return _httpClient.get(path);
  }

  Future<void> clearToken(String key) {
    return _secureStorage.delete(key: key);
  }
}
""".lstrip(),
                encoding="utf-8",
            )
            (root / "lib" / "features" / "products" / "models" / "product.dart").write_text(
                """
import 'package:freezed_annotation/freezed_annotation.dart';

part 'product.freezed.dart';
part 'product.g.dart';

@freezed
class Product with _$Product {
  const factory Product({
    required int id,
    required String title,
    double? price,
    @JsonKey(name: 'thumbnail_url') String? thumbnailUrl,
  }) = _Product;

  factory Product.fromJson(Map<String, dynamic> json) => _$ProductFromJson(json);
}
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {(framework.name, framework.category) for framework in facts.frameworks}
            self.assertIn(("flutter", "frontend"), frameworks)
            self.assertIn(("go-router", "frontend"), frameworks)
            self.assertIn(("riverpod", "frontend"), frameworks)
            self.assertIn(("flutter-hooks", "frontend"), frameworks)
            self.assertIn(("dio", "frontend"), frameworks)
            self.assertIn(("freezed", "frontend"), frameworks)

            routes = {(route.route, route.kind, route.path) for route in facts.frontend_routes}
            self.assertIn(("/products", "flutter-go-route", "lib/services/router.dart"), routes)
            self.assertIn(("/products/:id", "flutter-go-route", "lib/services/router.dart"), routes)
            self.assertIn(("/posts", "flutter-navigation-item-route", "lib/services/router.dart"), routes)
            self.assertIn(("/posts/:id", "flutter-go-route", "lib/services/router.dart"), routes)
            self.assertIn(("/todos", "flutter-go-route", "lib/services/router.dart"), routes)
            self.assertIn(("/todos/add", "flutter-go-route", "lib/services/router.dart"), routes)
            self.assertIn(("/todos/:id", "flutter-go-route", "lib/services/router.dart"), routes)
            self.assertIn(("/todos/:id/update", "flutter-go-route", "lib/services/router.dart"), routes)
            self.assertNotIn((":id", "flutter-go-route", "lib/services/router.dart"), routes)
            self.assertNotIn(("/add", "flutter-go-route", "lib/services/router.dart"), routes)
            self.assertNotIn(("/update", "flutter-go-route", "lib/services/router.dart"), routes)

            state = {(usage.library, usage.usage, usage.name, usage.source) for usage in facts.state_usages}
            self.assertIn(("riverpod", "scope", "ProviderScope", "lib/main.dart"), state)
            self.assertIn(("riverpod", "watch", "routerProvider", "lib/main.dart"), state)
            self.assertIn(("riverpod", "provider:Provider", "routerProvider", "lib/services/router.dart"), state)
            self.assertIn(("riverpod", "provider:@riverpod", "products", "lib/features/products/providers/products.dart"), state)
            self.assertIn(("riverpod", "watch", "productsProvider", "lib/features/products/screens/products.dart"), state)
            self.assertIn(("riverpod", "refresh", "productsProvider", "lib/features/products/screens/products.dart"), state)
            self.assertIn(("flutter-hooks", "hook", "useState", "lib/features/products/screens/products.dart"), state)
            self.assertFalse(any(usage.library == "react" and usage.source.endswith(".dart") for usage in facts.state_usages))

            api_calls = [
                call
                for call in facts.api_calls
                if call.path == "lib/services/api/api_client.dart" and call.endpoint == "/products/:id" and call.method == "GET"
            ]
            self.assertEqual(1, len(api_calls))
            self.assertEqual("_httpClient", api_calls[0].client)
            self.assertIn(
                ("POST", "/todos/add", "_httpClient"),
                {(call.method, call.endpoint, call.client) for call in facts.api_calls},
            )
            self.assertIn(
                ("GET", "/posts", "_httpClient", "dart-client-variable"),
                {(call.method, call.endpoint, call.client, call.context) for call in facts.api_calls},
            )
            self.assertFalse(any(call.client == "_secureStorage" for call in facts.api_calls))

            models = {(model.name, model.kind, model.path): model for model in facts.data_models}
            product = models[("Product", "dart-freezed-model", "lib/features/products/models/product.dart")]
            self.assertIn("id:int", product.fields)
            self.assertIn("title:String", product.fields)
            self.assertIn("price:double?", product.fields)
            self.assertIn("thumbnailUrl:String?", product.fields)
            self.assertIn("required:id", product.annotations)
            self.assertIn("required:title", product.annotations)
            self.assertIn("json-key:thumbnailUrl:thumbnail_url", product.annotations)
            self.assertIn("json-serializable", product.annotations)


if __name__ == "__main__":
    unittest.main()
