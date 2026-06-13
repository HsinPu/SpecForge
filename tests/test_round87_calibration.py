from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round87SwiftUICalibrationTests(unittest.TestCase):
    def test_swift_package_tca_models_state_entrypoints_and_test_map_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Package.swift").write_text(
                """
// swift-tools-version:5.9
import PackageDescription

let package = Package(
  name: "Demo",
  dependencies: [
    .package(url: "https://github.com/pointfreeco/swift-composable-architecture", from: "1.12.0"),
    .package(url: "https://github.com/pointfreeco/swift-snapshot-testing", from: "1.10.0"),
  ],
  targets: [
    .target(name: "HomeFeature"),
    .testTarget(name: "HomeFeatureTests", dependencies: ["HomeFeature"], exclude: ["__Snapshots__"]),
  ]
)
""".strip()
                + "\n",
                encoding="utf-8",
            )

            app_dir = root / "App" / "iOS"
            app_dir.mkdir(parents=True)
            (app_dir / "App.swift").write_text(
                """
import SwiftUI

@main
struct DemoApp: App {
  var body: some Scene {
    WindowGroup { HomeView(store: Store(initialState: Home.State()) { Home() }) }
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            feature_dir = root / "Sources" / "HomeFeature"
            feature_dir.mkdir(parents=True)
            (feature_dir / "Home.swift").write_text(
                """
import ComposableArchitecture
import SwiftUI

@Reducer
public struct Home {
  @ObservableState
  public struct State: Equatable {
    public var count: Int
    public var title: String?
  }

  public enum Action: Equatable {
    case tapped(Int)
  }
}

public struct HomeView: View {
  @Bindable var store: StoreOf<Home>

  public var body: some View {
    EmptyView()
  }
}

public struct SavedGamesState: Codable, Equatable {
  public var ids: [String]
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            leaderboard_dir = root / "Sources" / "LeaderboardFeature"
            leaderboard_dir.mkdir(parents=True)
            (leaderboard_dir / "LeaderboardView.swift").write_text(
                """
import SwiftUI

public struct LeaderboardView: View {
  public var body: some View { EmptyView() }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            demo_dir = root / "Sources" / "DemoFeature"
            demo_dir.mkdir(parents=True)
            (demo_dir / "Demo.swift").write_text(
                """
import SwiftUI

public struct DemoView: View {
  public var body: some View { EmptyView() }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            game_over_dir = root / "Sources" / "GameOverFeature"
            game_over_dir.mkdir(parents=True)
            (game_over_dir / "GameOverView.swift").write_text(
                """
import SwiftUI

public struct GameOverView: View {
  public var body: some View { EmptyView() }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            shared_models_dir = root / "Sources" / "SharedModels" / "API"
            shared_models_dir.mkdir(parents=True)
            (shared_models_dir / "SubmitGameResponse.swift").write_text(
                """
public enum SubmitGameResponse: Codable, Equatable {
  case solo

  public struct Response: Codable, Equatable {
    public let ok: Bool
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            tests_dir = root / "Tests" / "HomeFeatureTests"
            tests_dir.mkdir(parents=True)
            (tests_dir / "HomeFeatureTests.swift").write_text(
                """
import ComposableArchitecture
import HomeFeature
import XCTest

final class HomeFeatureTests: XCTestCase {
  func testReducer() {
    _ = TestStore(initialState: Home.State()) {
      Home()
    }
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (tests_dir / "HomeFeatureIntegrationTests.swift").write_text(
                """
import ComposableArchitecture
import HomeFeature
import XCTest

final class HomeFeatureIntegrationTests: XCTestCase {
  func testReducerBeatsComponentMention() {
    _ = "HomeView"
    _ = TestStore(initialState: Home.State()) {
      Home()
    }
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (tests_dir / "HomeViewTests.swift").write_text(
                """
import ComposableArchitecture
import HomeFeature
import XCTest

final class HomeViewTests: XCTestCase {
  func testHomeView() {
    _ = HomeView(store: Store(initialState: Home.State()) { Home() })
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            snapshots = tests_dir / "__Snapshots__"
            snapshots.mkdir()
            (snapshots / "HomeViewTests.json").write_text('{"snapshot": true}\n', encoding="utf-8")
            database_tests = root / "Tests" / "DatabaseLiveTests"
            database_tests.mkdir(parents=True)
            (database_tests / "FetchLeaderboardTests.swift").write_text(
                """
import XCTest

final class FetchLeaderboardTests: XCTestCase {
  func testFetchLeaderboard() {
    _ = "LeaderboardView"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (database_tests / "FetchWeekInReviewTests.swift").write_text(
                """
import XCTest

final class FetchWeekInReviewTests: XCTestCase {
  func testFetchWeekInReview() {
    _ = "LeaderboardView"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            middleware_integration_tests = root / "Tests" / "LeaderboardMiddlewareIntegrationTests"
            middleware_integration_tests.mkdir(parents=True)
            (middleware_integration_tests / "LeaderboardMiddlewareIntegrationTests.swift").write_text(
                """
import XCTest

final class LeaderboardMiddlewareIntegrationTests: XCTestCase {
  func testMiddleware() {
    _ = "LeaderboardView"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            shared_model_tests = root / "Tests" / "SharedModelsTests"
            shared_model_tests.mkdir(parents=True)
            (shared_model_tests / "SubmitGameResponseTests.swift").write_text(
                """
import SharedModels
import XCTest

final class SubmitGameResponseTests: XCTestCase {
  func testCodable() {
    _ = SubmitGameResponse.solo
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            game_over_tests = root / "Tests" / "GameOverFeatureTests"
            game_over_tests.mkdir(parents=True)
            (game_over_tests / "GameOverViewTests.swift").write_text(
                """
import GameOverFeature
import XCTest

final class GameOverViewTests: XCTestCase {
  func testGameOverView() {
    _ = GameOverView()
    _ = "isDemo"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            dependencies = {(item.name, item.scope, item.source) for item in facts.dependencies}
            self.assertIn(("swift-composable-architecture", "swift-package", "Package.swift"), dependencies)
            self.assertIn(("swift-snapshot-testing", "swift-package", "Package.swift"), dependencies)

            frameworks = {(item.name, item.category) for item in facts.frameworks}
            self.assertIn(("tca", "frontend"), frameworks)
            self.assertIn(("swiftui", "frontend"), frameworks)

            commands = {(item.name, tuple(item.arguments), item.path) for item in facts.commands}
            self.assertIn(("swift build", ("build",), "Package.swift"), commands)
            self.assertIn(("swift test", ("test",), "Package.swift"), commands)
            self.assertIn(("swift package resolve", ("package", "resolve"), "Package.swift"), commands)

            entrypoints = {(item.kind, item.path, item.command) for item in facts.entrypoints}
            self.assertIn(("swiftui-app", "App/iOS/App.swift", "swift build"), entrypoints)

            models = {(item.name, item.kind) for item in facts.data_models}
            self.assertIn(("Home", "tca-reducer"), models)
            self.assertIn(("Home.State", "tca-state"), models)
            self.assertIn(("Home.Action", "tca-action"), models)
            self.assertIn(("SavedGamesState", "swift-codable-model"), models)
            state_model = next(item for item in facts.data_models if item.name == "Home.State")
            self.assertIn("count:Int", state_model.fields)
            self.assertIn("optional:title", state_model.annotations)

            state_usages = {(item.library, item.usage, item.name) for item in facts.state_usages}
            self.assertIn(("tca", "reducer", "Home"), state_usages)
            self.assertIn(("tca", "observable-state", "State"), state_usages)
            self.assertIn(("tca", "bindable-store", "store:Home"), state_usages)
            self.assertIn(("tca", "store-init", "Home"), state_usages)

            test_maps = {item.test_path: item for item in facts.test_maps}
            self.assertEqual("data-model", test_maps["Tests/HomeFeatureTests/HomeFeatureTests.swift"].target_kind)
            self.assertEqual("Home", test_maps["Tests/HomeFeatureTests/HomeFeatureTests.swift"].target)
            self.assertEqual("high", test_maps["Tests/HomeFeatureTests/HomeFeatureTests.swift"].confidence)
            self.assertEqual("data-model", test_maps["Tests/HomeFeatureTests/HomeFeatureIntegrationTests.swift"].target_kind)
            self.assertEqual("Home", test_maps["Tests/HomeFeatureTests/HomeFeatureIntegrationTests.swift"].target)
            self.assertEqual("component", test_maps["Tests/HomeFeatureTests/HomeViewTests.swift"].target_kind)
            self.assertEqual("HomeView", test_maps["Tests/HomeFeatureTests/HomeViewTests.swift"].target)
            self.assertEqual("unmatched", test_maps["Tests/DatabaseLiveTests/FetchLeaderboardTests.swift"].target_kind)
            self.assertEqual("unmatched", test_maps["Tests/DatabaseLiveTests/FetchWeekInReviewTests.swift"].target_kind)
            self.assertEqual("unmatched", test_maps["Tests/LeaderboardMiddlewareIntegrationTests/LeaderboardMiddlewareIntegrationTests.swift"].target_kind)
            self.assertEqual("data-model", test_maps["Tests/SharedModelsTests/SubmitGameResponseTests.swift"].target_kind)
            self.assertEqual("SubmitGameResponse", test_maps["Tests/SharedModelsTests/SubmitGameResponseTests.swift"].target)
            self.assertEqual("high", test_maps["Tests/SharedModelsTests/SubmitGameResponseTests.swift"].confidence)
            self.assertEqual("component", test_maps["Tests/GameOverFeatureTests/GameOverViewTests.swift"].target_kind)
            self.assertEqual("GameOverView", test_maps["Tests/GameOverFeatureTests/GameOverViewTests.swift"].target)
            self.assertEqual("high", test_maps["Tests/GameOverFeatureTests/GameOverViewTests.swift"].confidence)
            self.assertNotIn("Tests/HomeFeatureTests/__Snapshots__/HomeViewTests.json", test_maps)


if __name__ == "__main__":
    unittest.main()
