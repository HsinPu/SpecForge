from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round55AspNetCalibrationTests(unittest.TestCase):
    def test_aspnet_minimal_endpoint_classes_and_csharp_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            endpoint_dir = root / "src" / "PublicApi" / "CatalogItemEndpoints"
            entity_dir = root / "src" / "ApplicationCore" / "Entities"
            endpoint_dir.mkdir(parents=True)
            entity_dir.mkdir(parents=True)
            (root / "src" / "PublicApi" / "PublicApi.csproj").parent.mkdir(parents=True, exist_ok=True)
            (root / "src" / "PublicApi" / "PublicApi.csproj").write_text(
                """
<Project Sdk="Microsoft.NET.Sdk.Web">
  <ItemGroup>
    <PackageReference Include="MinimalApi.Endpoint" Version="1.0.0" />
    <PackageReference Include="Swashbuckle.AspNetCore" Version="6.0.0" />
  </ItemGroup>
</Project>
""".lstrip(),
                encoding="utf-8",
            )
            (endpoint_dir / "CreateCatalogItemEndpoint.cs").write_text(
                """
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using MinimalApi.Endpoint;

public class CreateCatalogItemEndpoint : IEndpoint<IResult, CreateCatalogItemRequest>
{
    public void AddRoute(IEndpointRouteBuilder app)
    {
        app.MapPost("api/catalog-items",
            async (CreateCatalogItemRequest request) =>
            {
                return await HandleAsync(request);
            })
            .Produces<CreateCatalogItemResponse>()
            .WithTags("CatalogItemEndpoints");
    }
}
""".lstrip(),
                encoding="utf-8",
            )
            (endpoint_dir / "CatalogItemGetByIdEndpoint.cs").write_text(
                """
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using MinimalApi.Endpoint;

public class CatalogItemGetByIdEndpoint : IEndpoint<IResult, GetByIdCatalogItemRequest>
{
    public void AddRoute(IEndpointRouteBuilder app)
    {
        app.MapGet("api/catalog-items/{catalogItemId}",
            async (int catalogItemId) =>
            {
                return await HandleAsync(new GetByIdCatalogItemRequest(catalogItemId));
            })
            .Produces<GetByIdCatalogItemResponse>();
    }
}
""".lstrip(),
                encoding="utf-8",
            )
            (endpoint_dir / "CreateCatalogItemEndpoint.CreateCatalogItemRequest.cs").write_text(
                """
public class CreateCatalogItemRequest : BaseRequest
{
    public int CatalogTypeId { get; init; }
    public string Name { get; init; }
}
""".lstrip(),
                encoding="utf-8",
            )
            (endpoint_dir / "CreateCatalogItemEndpoint.CreateCatalogItemResponse.cs").write_text(
                """
public class CreateCatalogItemResponse : BaseResponse
{
    public CatalogItemDto CatalogItem { get; set; }
}
""".lstrip(),
                encoding="utf-8",
            )
            (entity_dir / "CatalogItem.cs").write_text(
                """
public class CatalogItem : BaseEntity, IAggregateRoot
{
    public string Name { get; private set; }
    public decimal Price { get; private set; }
    public CatalogBrand? CatalogBrand { get; private set; }

    public readonly record struct CatalogItemDetails
    {
        public string? InternalName { get; }
    }
}
""".lstrip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.method, route.path, route.handler, route.kind, route.response_type) for route in facts.api_routes}
            self.assertIn(
                ("POST", "/api/catalog-items", "CreateCatalogItemEndpoint", "aspnetcore-minimal-route", "CreateCatalogItemResponse"),
                routes,
            )
            self.assertIn(
                ("GET", "/api/catalog-items/{catalogItemId}", "CatalogItemGetByIdEndpoint", "aspnetcore-minimal-route", "GetByIdCatalogItemResponse"),
                routes,
            )
            route = next(item for item in facts.api_routes if item.path == "/api/catalog-items/{catalogItemId}")
            self.assertEqual(["catalogItemId"], [param.name for param in route.parameters])

            contracts = {(contract.method, contract.path, contract.response_type) for contract in facts.api_contracts}
            self.assertIn(("POST", "/api/catalog-items", "CreateCatalogItemResponse"), contracts)

            models = {(model.name, model.kind, model.path): model for model in facts.data_models}
            entity = models[("CatalogItem", "csharp-entity", "src/ApplicationCore/Entities/CatalogItem.cs")]
            self.assertIn("Name:string", entity.fields)
            self.assertIn("Price:decimal", entity.fields)
            self.assertIn("CatalogBrand:CatalogBrand?", entity.fields)
            self.assertNotIn("InternalName:string?", entity.fields)
            self.assertIn("bases:BaseEntity, IAggregateRoot", entity.annotations)
            self.assertIn("private-set:Name", entity.annotations)

            request = models[
                (
                    "CreateCatalogItemRequest",
                    "csharp-request",
                    "src/PublicApi/CatalogItemEndpoints/CreateCatalogItemEndpoint.CreateCatalogItemRequest.cs",
                )
            ]
            self.assertIn("CatalogTypeId:int", request.fields)
            self.assertIn("Name:string", request.fields)
            self.assertIn("init-only:Name", request.annotations)

            response = models[
                (
                    "CreateCatalogItemResponse",
                    "csharp-response",
                    "src/PublicApi/CatalogItemEndpoints/CreateCatalogItemEndpoint.CreateCatalogItemResponse.cs",
                )
            ]
            self.assertIn("CatalogItem:CatalogItemDto", response.fields)


if __name__ == "__main__":
    unittest.main()
