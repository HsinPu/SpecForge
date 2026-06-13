from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round147ComposeNavigationCalibrationTests(unittest.TestCase):
    def test_android_compose_navigation_entries_and_routes_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "settings.gradle.kts").write_text('pluginManagement { repositories { google() } }\ninclude(":app")\n', encoding="utf-8")
            app = root / "app"
            app.mkdir()
            (app / "build.gradle.kts").write_text(
                """
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android { namespace = "demo.app" }

dependencies {
    implementation("androidx.compose.ui:ui:1.7.0")
    implementation("androidx.navigation:navigation-compose:2.8.0")
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            manifest = app / "src" / "main" / "AndroidManifest.xml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("<manifest package=\"demo.app\" />\n", encoding="utf-8")
            nav_file = app / "src" / "main" / "kotlin" / "demo" / "Navigation.kt"
            nav_file.parent.mkdir(parents=True)
            nav_file.write_text(
                """
package demo

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.navigation
import androidx.navigation3.runtime.EntryProviderScope
import androidx.navigation3.runtime.NavKey

object SettingsNavKey : NavKey
data class ProfileNavKey(val id: String) : NavKey
data class DetailRoute(val id: String) : NavKey

fun EntryProviderScope<NavKey>.settingsEntry() {
    entry<SettingsNavKey> {
        SettingsScreen()
    }
    entry<ProfileNavKey>(
        metadata = "detail",
    ) { key ->
        ProfileScreen(key.id)
    }
    // entry<CommentedNavKey> { CommentedScreen() }
}

@Composable
fun AppNavigation(navController: NavHostController) {
    NavHost(navController = navController, startDestination = "home") {
        composable(route = "home") {
            HomeScreen()
        }
        navigation(startDestination = "feed", route = "main") {
            composable("feed") {
                FeedScreen()
            }
        }
        composable<DetailRoute> {
            DetailScreen()
        }
    }
}

@Composable fun HomeScreen() {}
@Composable fun SettingsScreen() {}
@Composable fun ProfileScreen(id: String) {}
@Composable fun FeedScreen() {}
@Composable fun DetailScreen() {}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.framework, route.kind, route.route, route.path) for route in facts.frontend_routes}
            self.assertIn(
                ("jetpack-compose", "compose-navigation3-entry", "/SettingsNavKey", "app/src/main/kotlin/demo/Navigation.kt"),
                routes,
            )
            self.assertIn(
                ("jetpack-compose", "compose-navigation3-entry", "/ProfileNavKey", "app/src/main/kotlin/demo/Navigation.kt"),
                routes,
            )
            self.assertIn(
                ("jetpack-compose", "compose-navigation-route", "/home", "app/src/main/kotlin/demo/Navigation.kt"),
                routes,
            )
            self.assertIn(
                ("jetpack-compose", "compose-navigation-graph", "/main", "app/src/main/kotlin/demo/Navigation.kt"),
                routes,
            )
            self.assertIn(
                ("jetpack-compose", "compose-navigation-route", "/feed", "app/src/main/kotlin/demo/Navigation.kt"),
                routes,
            )
            self.assertIn(
                ("jetpack-compose", "compose-navigation-route", "/DetailRoute", "app/src/main/kotlin/demo/Navigation.kt"),
                routes,
            )
            self.assertNotIn(
                ("jetpack-compose", "compose-navigation3-entry", "/CommentedNavKey", "app/src/main/kotlin/demo/Navigation.kt"),
                routes,
            )


if __name__ == "__main__":
    unittest.main()
