from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from specforge.scanner import scan_project


class Round13CalibrationTests(unittest.TestCase):

    def test_scan_project_detects_auth_security_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                """
{
  "dependencies": {
    "@nestjs/common": "^10.0.0",
    "@nestjs/passport": "^10.0.0",
    "@nestjs/jwt": "^10.0.0",
    "next-auth": "^4.0.0",
    "passport": "^0.7.0",
    "passport-jwt": "^4.0.0",
    "jsonwebtoken": "^9.0.0",
    "bcrypt": "^5.0.0",
    "helmet": "^7.0.0",
    "csurf": "^1.0.0"
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            src = root / "src"
            src.mkdir()
            (src / "auth.controller.ts").write_text(
                """
import { Controller, Post, UseGuards } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';

@Controller('auth')
export class AuthController {
  @Post('logout')
  @UseGuards(AuthGuard('jwt'))
  async logout() {
    return { ok: true };
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (src / "auth.ts").write_text(
                """
import NextAuth from 'next-auth';
import GitHubProvider from 'next-auth/providers/github';
import bcrypt from 'bcrypt';

export const authOptions = {
  secret: process.env.NEXTAUTH_SECRET,
  providers: [GitHubProvider({ clientId: process.env.GITHUB_CLIENT_ID, clientSecret: process.env.GITHUB_CLIENT_SECRET })],
};

export default NextAuth(authOptions);
bcrypt.hash('secret', 10);
""".strip()
                + "\n",
                encoding="utf-8",
            )
            java_dir = root / "src" / "main" / "java" / "demo"
            java_dir.mkdir(parents=True)
            (java_dir / "SecurityConfig.java").write_text(
                """
package demo;

import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.web.SecurityFilterChain;

@EnableWebSecurity
public class SecurityConfig {
  SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
    return http.authorizeHttpRequests(auth -> auth
      .requestMatchers("/api/auth/**").permitAll()
      .requestMatchers("/admin/**").hasRole("ADMIN")
    ).build();
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "settings.py").write_text(
                """
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    )
}
SIMPLE_JWT = {"SIGNING_KEY": "example"}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "main.py").write_text(
                """
from fastapi.security import OAuth2PasswordBearer
import jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
payload = jwt.decode("token", "secret", algorithms=["HS256"])
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (root / "Program.cs").write_text(
                """
using Microsoft.AspNetCore.Authentication.JwtBearer;

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
  .AddJwtBearer(options => {});
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            for framework in {
                "nestjs",
                "nextauth",
                "passport",
                "jwt",
                "bcrypt",
                "spring-security",
                "django-simplejwt",
                "fastapi-jwt",
                "aspnetcore-jwt",
            }:
                self.assertIn(framework, frameworks)

            api_routes = {(route.framework, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("nestjs", "POST", "/auth/logout", "logout"), api_routes)
            self.assertNotIn(("nestjs", "POST", "/auth/logout", "UseGuards"), api_routes)

            security_values = {
                value
                for item in facts.runtime_configs
                if item.kind == "security-surface"
                for value in item.values
            }
            self.assertIn("security-signal:nextauth", security_values)
            self.assertIn("security-signal:jwt", security_values)
            self.assertIn("security-signal:bcrypt", security_values)
            self.assertIn("security-signal:spring-security", security_values)
            self.assertIn("security-signal:aspnetcore-jwt", security_values)
            self.assertIn("env-key:NEXTAUTH_SECRET", security_values)
            self.assertIn("env-key:GITHUB_CLIENT_ID", security_values)
            self.assertIn("auth-guard:AuthGuard('jwt'", security_values)
            self.assertIn("authorize-pattern:/api/auth/**", security_values)
            self.assertIn("permission:ADMIN", security_values)
            self.assertIn("django-auth-class:JWTAuthentication", security_values)
            self.assertIn("fastapi-security:OAuth2PasswordBearer", security_values)


if __name__ == "__main__":
    unittest.main()
