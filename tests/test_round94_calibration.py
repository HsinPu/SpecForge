from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round94AspNetCalibrationTests(unittest.TestCase):
    def test_aspnet_controller_tokens_route_method_merge_and_endpointbase_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            (src / "Demo.csproj").write_text(
                """
<Project Sdk="Microsoft.NET.Sdk.Web">
  <ItemGroup>
    <PackageReference Include="Microsoft.AspNetCore.Mvc" Version="8.0.0" />
  </ItemGroup>
</Project>
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (src / "OrderController.cs").write_text(
                """
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

[Authorize]
[Route("[controller]/[action]")]
public class OrderController : Controller
{
    [HttpGet]
    public async Task<IActionResult> MyOrders()
    {
        return View();
    }

    [HttpGet("{orderId}")]
    public async Task<IActionResult> Detail(int orderId)
    {
        return View();
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (src / "UserController.cs").write_text(
                """
using Microsoft.AspNetCore.Mvc;

[Route("[controller]")]
public class UserController : Controller
{
    [Route("Logout")]
    [HttpPost]
    public async Task<IActionResult> Logout()
    {
        return Redirect("/");
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (src / "AuthenticateEndpoint.cs").write_text(
                """
using System.Threading;
using Ardalis.ApiEndpoints;
using Microsoft.AspNetCore.Mvc;
using Swashbuckle.AspNetCore.Annotations;

public class AuthenticateRequest {}
public class AuthenticateResponse {}

public class AuthenticateEndpoint : EndpointBaseAsync
    .WithRequest<AuthenticateRequest>
    .WithActionResult<AuthenticateResponse>
{
    [HttpPost("api/authenticate")]
    [SwaggerOperation(
        Summary = "Authenticates a user",
        OperationId = "auth.authenticate",
        Tags = new[] { "AuthEndpoints" })]
    public override async Task<ActionResult<AuthenticateResponse>> HandleAsync(AuthenticateRequest request,
        CancellationToken cancellationToken = default)
    {
        return new AuthenticateResponse();
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (src / "appsettings.Docker.json").write_text(
                """
{
  "ConnectionStrings": {
    "CatalogConnection": "Server=sqlserver,1433;User Id=sa;Password=@someThingComplicated1234;"
  },
  "baseUrls": {
    "apiBase": "http://localhost:5200/api/",
    "webBase": "http://host.docker.internal:5106/"
  },
  "Logging": {
    "LogLevel": {
      "Default": "Debug",
      "Microsoft": "Information"
    }
  },
  "AllowedHosts": "*"
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {
                (route.method, route.path): route
                for route in facts.api_routes
                if route.framework == "aspnetcore"
            }
            self.assertIn(("GET", "/order/MyOrders"), routes)
            self.assertIn(("GET", "/order/Detail/{orderId}"), routes)
            self.assertIn(("POST", "/user/Logout"), routes)
            self.assertIn(("POST", "/api/authenticate"), routes)
            self.assertNotIn(("POST", "/user"), routes)
            self.assertNotIn(("ANY", "/user/Logout"), routes)

            detail_params = {
                (param.source, param.name, param.type)
                for param in routes[("GET", "/order/Detail/{orderId}")].parameters
            }
            self.assertIn(("path", "orderId", None), detail_params)
            self.assertEqual("Detail", routes[("GET", "/order/Detail/{orderId}")].handler)

            authenticate = routes[("POST", "/api/authenticate")]
            self.assertEqual("HandleAsync", authenticate.handler)
            self.assertEqual("Task<ActionResult<AuthenticateResponse>>", authenticate.response_type)

            runtime = {(fact.path, fact.kind): fact for fact in facts.runtime_configs}
            self.assertIn(("src/appsettings.Docker.json", "aspnet-appsettings"), runtime)
            appsettings = runtime[("src/appsettings.Docker.json", "aspnet-appsettings")]
            self.assertIn("environment:Docker", appsettings.values)
            self.assertIn("connection-string-key:CatalogConnection", appsettings.values)
            self.assertIn("url-key:baseUrls.apiBase", appsettings.values)
            self.assertIn("port:5200", appsettings.values)
            self.assertIn("log-level:Default=Debug", appsettings.values)
            self.assertIn("allowed-hosts:configured", appsettings.values)
            self.assertNotIn("@someThingComplicated1234", " ".join(appsettings.values))


if __name__ == "__main__":
    unittest.main()
