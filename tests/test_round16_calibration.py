from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round16CalibrationTests(unittest.TestCase):

    def test_scan_project_detects_native_app_surfaces_and_tolerates_legacy_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "expo": "^52.0.0",
    "react": "^19.0.0",
    "react-native": "^0.76.0",
    "expo-router": "^4.0.0",
    "@react-navigation/native": "^7.0.0",
    "@ionic/react": "^8.0.0",
    "@nativescript/core": "^8.0.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            expo_home = root / "app" / "(tabs)"
            expo_home.mkdir(parents=True)
            (expo_home / "index.tsx").write_text(
                """
import { Text, View } from 'react-native';

export default function HomeScreen() {
  return <View><Text>Home</Text></View>;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            expo_user = root / "app" / "users"
            expo_user.mkdir(parents=True)
            (expo_user / "[id].tsx").write_text(
                """
import { useEffect } from 'react';

export default function UserScreen() {
  useEffect(() => {
    fetch('/api/users/123');
  }, []);
  return null;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            nav = root / "src" / "navigation"
            nav.mkdir(parents=True)
            (nav / "AppNavigator.tsx").write_text(
                """
import { createNativeStackNavigator } from '@react-navigation/native-stack';

const Stack = createNativeStackNavigator();

export function AppNavigator() {
  return <Stack.Screen name="Settings" component={SettingsScreen} />;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            swift = root / "SwiftApp"
            swift.mkdir()
            (swift / "OrdersView.swift").write_text(
                """
import SwiftUI

struct OrdersView: View {
    @State private var orderCount = 0

    var body: some View {
        Text("Orders")
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            maui = root / "MauiApp"
            maui.mkdir()
            (maui / "MauiApp.csproj").write_text(
                """
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFrameworks>net9.0-android;net9.0-ios</TargetFrameworks>
    <UseMaui>true</UseMaui>
  </PropertyGroup>
</Project>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (maui / "MainPage.xaml").write_text(
                """
<ContentPage
    x:Class="Demo.Maui.MainPage"
    xmlns="http://schemas.microsoft.com/dotnet/2021/maui"
    xmlns:x="http://schemas.microsoft.com/winfx/2009/xaml">
    <Button x:Name="SaveButton" Clicked="OnSaveClicked" />
</ContentPage>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            maui_windows = maui / "Platforms" / "Windows"
            maui_windows.mkdir(parents=True)
            (maui_windows / "App.xaml").write_text(
                """
<maui:MauiWinUIApplication
    x:Class="Demo.Maui.WinApp"
    xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
    xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
    xmlns:maui="using:Microsoft.Maui" />
""".strip()
                + "\n",
                encoding="utf-8",
            )

            wpf = root / "WpfApp"
            wpf.mkdir()
            (wpf / "WpfApp.csproj").write_text(
                """
<Project Sdk="Microsoft.NET.Sdk.WindowsDesktop">
  <PropertyGroup>
    <TargetFramework>net10.0-windows</TargetFramework>
    <UseWPF>true</UseWPF>
  </PropertyGroup>
</Project>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (wpf / "Program.cs").write_text(
                """
public static class Program
{
    public static void Main() {}
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (wpf / "ShellWindow.xaml").write_text(
                """
<Window
    x:Class="Demo.Wpf.ShellWindow"
    xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
    xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">
    <Grid Name="RootGrid" Loaded="OnLoaded" />
</Window>
""".strip()
                + "\n",
                encoding="utf-8",
            )

            avalonia = root / "AvaloniaApp"
            avalonia.mkdir()
            (avalonia / "AvaloniaApp.csproj").write_text(
                """
<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <PackageReference Include="Avalonia" Version="11.0.0" />
  </ItemGroup>
</Project>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (avalonia / "DashboardView.axaml").write_text(
                """
<UserControl
    x:Class="Demo.Avalonia.DashboardView"
    xmlns="https://github.com/avaloniaui"
    xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">
    <Button Name="RefreshButton" Command="{Binding Refresh}" />
</UserControl>
""".strip()
                + "\n",
                encoding="utf-8",
            )

            public = root / "public"
            public.mkdir()
            (public / "legacy.html").write_bytes(b"<html><title>Don\x92t crash</title></html>")

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertTrue(
                {
                    "avalonia",
                    "expo",
                    "ios",
                    "maui",
                    "nativescript",
                    "react-native",
                    "react-navigation",
                    "swiftui",
                    "wpf",
                }
                <= frameworks
            )
            self.assertNotIn("aspnetcore", frameworks)

            routes = {(route.framework, route.route) for route in facts.frontend_routes}
            self.assertIn(("expo", "/"), routes)
            self.assertIn(("expo", "/users/:id"), routes)
            self.assertIn(("react-navigation", "/Settings"), routes)

            components = {(component.framework, component.name) for component in facts.components}
            self.assertIn(("swiftui", "OrdersView"), components)
            self.assertIn(("maui", "MainPage"), components)
            self.assertIn(("maui", "WinApp"), components)
            self.assertIn(("wpf", "ShellWindow"), components)
            self.assertIn(("avalonia", "DashboardView"), components)

            state = {(usage.library, usage.name) for usage in facts.state_usages}
            self.assertIn(("swiftui", "@State orderCount"), state)

            calls = {(call.client, call.endpoint) for call in facts.api_calls}
            self.assertIn(("fetch", "/api/users/123"), calls)
            self.assertIn("public/legacy.html", {page.path for page in facts.pages})


if __name__ == "__main__":
    unittest.main()
