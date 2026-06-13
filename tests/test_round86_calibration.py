from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round86AndroidKotlinCalibrationTests(unittest.TestCase):
    def test_android_kotlin_compose_gradle_models_state_and_test_map_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "gradlew").write_text("#!/bin/sh\n", encoding="utf-8")
            (root / "settings.gradle.kts").write_text(
                """
pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }
dependencyResolutionManagement { repositoriesMode = RepositoriesMode.FAIL_ON_PROJECT_REPOS }
rootProject.name = "demo"
include(":app")
include(":core:data")
include(":core:model")
""".strip()
                + "\n",
                encoding="utf-8",
            )
            app = root / "app"
            app.mkdir()
            (app / "build.gradle.kts").write_text(
                """
plugins {
    alias(libs.plugins.nowinandroid.android.application)
    alias(libs.plugins.nowinandroid.android.application.compose)
}

android { namespace = "demo.app" }
""".strip()
                + "\n",
                encoding="utf-8",
            )
            manifest = app / "src" / "main" / "AndroidManifest.xml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("<manifest package=\"demo.app\" />\n", encoding="utf-8")

            app_ui = app / "src" / "main" / "kotlin" / "demo"
            app_ui.mkdir(parents=True)
            (app_ui / "MainActivity.kt").write_text(
                """
package demo

import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.flow.StateFlow

class ForYouViewModel : ViewModel() {
    val feedState: StateFlow<NewsFeedUiState> = TODO()
}

@Composable
fun NiaTheme(content: @Composable () -> Unit) {
    CompositionLocalProvider {
        content()
    }
}

@Composable
fun ForYouScreen(viewModel: ForYouViewModel) {
    val feedState by viewModel.feedState.collectAsStateWithLifecycle()
    var showSettingsDialog by rememberSaveable { mutableStateOf(false) }
    NiaTheme {}
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            model_dir = root / "core" / "model" / "src" / "main" / "kotlin" / "demo" / "model"
            model_dir.mkdir(parents=True)
            (model_dir / "NewsResource.kt").write_text(
                """
package demo.model

data class NewsResource(
    val id: String,
    val title: String,
)

data class NewsFeedUiState(
    val resources: List<NewsResource>,
)
""".strip()
                + "\n",
                encoding="utf-8",
            )
            database_dir = root / "core" / "data" / "src" / "main" / "kotlin" / "demo" / "database" / "model"
            database_dir.mkdir(parents=True)
            (database_dir / "NewsResourceEntity.kt").write_text(
                """
package demo.database.model

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(
    tableName = "news_resources",
)
data class NewsResourceEntity(
    @PrimaryKey val id: String,
    val title: String,
)
""".strip()
                + "\n",
                encoding="utf-8",
            )
            repository_dir = root / "core" / "data" / "src" / "main" / "kotlin" / "demo" / "repository"
            repository_dir.mkdir(parents=True)
            (repository_dir / "OfflineFirstUserDataRepository.kt").write_text(
                "class OfflineFirstUserDataRepository\n",
                encoding="utf-8",
            )
            repository_test_dir = root / "core" / "data" / "src" / "test" / "kotlin" / "demo" / "repository"
            repository_test_dir.mkdir(parents=True)
            (repository_test_dir / "OfflineFirstUserDataRepositoryTest.kt").write_text(
                """
class OfflineFirstUserDataRepositoryTest {
    fun mapsRepositoryEvenWhenThemeIsMentioned() {
        OfflineFirstUserDataRepository()
        NiaTheme {}
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            screenshots = app / "src" / "testDemo" / "screenshots"
            screenshots.mkdir(parents=True)
            (screenshots / "compactWidth_showsNavigationBar.png").write_bytes(b"not-a-real-png")

            facts = scan_project(root)

            entrypoints = {(item.kind, item.path, item.command) for item in facts.entrypoints}
            self.assertIn(
                (
                    "android-app",
                    "app/src/main/AndroidManifest.xml",
                    "./gradlew :app:installDebug",
                ),
                entrypoints,
            )
            commands = {(item.name, tuple(item.arguments), item.path) for item in facts.commands}
            self.assertIn(("./gradlew build", ("build",), "settings.gradle.kts"), commands)
            self.assertIn(("./gradlew :app:assembleDebug", (":app:assembleDebug",), "app/build.gradle.kts"), commands)

            models = {(item.name, item.kind) for item in facts.data_models}
            self.assertIn(("NewsResource", "kotlin-data-class"), models)
            self.assertIn(("NewsFeedUiState", "kotlin-ui-state"), models)
            self.assertIn(("NewsResourceEntity", "kotlin-room-entity"), models)
            entity = next(item for item in facts.data_models if item.name == "NewsResourceEntity")
            self.assertIn("table:news_resources", entity.annotations)
            self.assertIn("title:String", entity.fields)

            state = {(item.library, item.usage, item.name) for item in facts.state_usages}
            self.assertIn(("androidx-lifecycle", "viewmodel", "ForYouViewModel"), state)
            self.assertIn(("kotlin-flow", "state-flow", "feedState"), state)
            self.assertIn(("androidx-lifecycle-compose", "collect-as-state", "feedState"), state)
            self.assertIn(("jetpack-compose", "mutable-state", "showSettingsDialog"), state)

            security_paths = {item.path for item in facts.runtime_configs if item.kind == "security-surface"}
            self.assertNotIn("app/src/main/kotlin/demo/MainActivity.kt", security_paths)

            test_maps = {item.test_path: item for item in facts.test_maps}
            repository_test = "core/data/src/test/kotlin/demo/repository/OfflineFirstUserDataRepositoryTest.kt"
            self.assertEqual("repository", test_maps[repository_test].target_kind)
            self.assertEqual("OfflineFirstUserDataRepository", test_maps[repository_test].target)
            self.assertNotIn("app/src/testDemo/screenshots/compactWidth_showsNavigationBar.png", test_maps)


if __name__ == "__main__":
    unittest.main()
