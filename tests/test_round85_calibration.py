from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round85AspNetNopCommerceCalibrationTests(unittest.TestCase):
    def test_nopcommerce_style_route_providers_and_conventional_actions_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            web = root / "src" / "Presentation" / "Nop.Web"
            web.mkdir(parents=True)
            (root / "src" / "NopCommerce.sln").write_text(
                "Microsoft Visual Studio Solution File, Format Version 12.00\n",
                encoding="utf-8",
            )
            (web / "Nop.Web.csproj").write_text(
                '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>\n',
                encoding="utf-8",
            )
            (web / "Program.cs").write_text(
                """
var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();
app.UseEndpoints(endpoints =>
{
    endpoints.MapControllerRoute(name: "areaRoute",
        pattern: "{area:exists}/{controller=Home}/{action=Index}/{id?}");
});
app.Run();
""".strip()
                + "\n",
                encoding="utf-8",
            )
            infra = web / "Infrastructure"
            infra.mkdir()
            (infra / "RouteProvider.cs").write_text(
                """
public partial class RouteProvider : BaseRouteProvider, IRouteProvider
{
    public virtual void RegisterRoutes(IEndpointRouteBuilder endpointRouteBuilder)
    {
        var lang = GetLanguageRoutePattern();
        endpointRouteBuilder.MapControllerRoute(name: NopRouteNames.General.LOGIN,
            pattern: $"{lang}/login/",
            defaults: new { controller = "Customer", action = "Login" });

        endpointRouteBuilder.MapControllerRoute(name: NopRouteNames.Ajax.ESTIMATE_SHIPPING,
            pattern: "cart/estimateshipping",
            defaults: new { controller = "ShoppingCart", action = "GetEstimateShipping" });

        var genericCatalogPattern = $"{lang}/{{{NopRoutingDefaults.RouteValue.CatalogSeName}}}/{{{NopRoutingDefaults.RouteValue.SeName}}}";
        endpointRouteBuilder.MapDynamicControllerRoute<SlugRouteTransformer>(genericCatalogPattern);

        var genericPattern = $"{lang}/{{{NopRoutingDefaults.RouteValue.SeName}}}";
        endpointRouteBuilder.MapControllerRoute(name: NopRoutingDefaults.RouteName.Generic.Product,
            pattern: genericPattern,
            defaults: new { controller = "Product", action = "ProductDetails" });
        endpointRouteBuilder.MapControllerRoute(name: NopRoutingDefaults.RouteName.Generic.Category,
            pattern: genericPattern,
            defaults: new { controller = "Catalog", action = "Category" });

        endpointRouteBuilder.MapControllerRoute(name: "NewsItem",
            pattern: $"{GetLanguageRoutePattern()}/{{{NopRoutingDefaults.RouteValue.SeName}}}",
            defaults: new { controller = "News", action = "NewsItem" });
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            plugin = root / "src" / "Plugins" / "Nop.Plugin.Widgets.FacebookPixel"
            (plugin / "Infrastructure").mkdir(parents=True)
            (plugin / "Controllers").mkdir()
            (plugin / "Infrastructure" / "RouteProvider.cs").write_text(
                """
public class RouteProvider : IRouteProvider
{
    public void RegisterRoutes(IEndpointRouteBuilder endpointRouteBuilder)
    {
        endpointRouteBuilder.MapControllerRoute(FacebookPixelDefaults.ConfigurationRouteName, "Plugins/FacebookPixel/Configure",
            new { controller = "FacebookPixel", action = "Configure", area = AreaNames.ADMIN });
    }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (plugin / "Controllers" / "FacebookPixelController.cs").write_text(
                """
[Area(AreaNames.ADMIN)]
public class FacebookPixelController : Controller
{
    [HttpPost, ActionName("Configure")]
    public virtual Task<IActionResult> SaveConfigure(FacebookPixelModel model) => Task.FromResult<IActionResult>(Ok());
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            admin_controller = web / "Areas" / "Admin" / "Controllers"
            admin_controller.mkdir(parents=True)
            (admin_controller / "ProductController.cs").write_text(
                """
public class ProductController : Controller
{
    [HttpPost]
    public virtual Task<IActionResult> ProductList(ProductSearchModel searchModel) => Task.FromResult<IActionResult>(Json(searchModel));
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            inventory_api = root / "src" / "Plugins" / "Nop.Plugin.Misc.Zettle" / "Domain" / "Api" / "Inventory"
            inventory_api.mkdir(parents=True)
            (inventory_api / "InventoryApiRequest.cs").write_text(
                """
namespace Nop.Plugin.Misc.Zettle.Domain.Api.Inventory;

public class InventoryApiRequest
{
    public string LocationId { get; set; }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            catalog_domain = root / "src" / "Libraries" / "Nop.Core" / "Domain" / "Catalog"
            catalog_domain.mkdir(parents=True)
            (catalog_domain / "Product.cs").write_text(
                """
namespace Nop.Core.Domain.Catalog;

public class Product : BaseEntity
{
    public string Name { get; set; }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            common_domain = root / "src" / "Libraries" / "Nop.Core" / "Domain" / "Common"
            common_domain.mkdir(parents=True)
            (common_domain / "Address.cs").write_text(
                """
namespace Nop.Core.Domain.Common;

public class Address : BaseEntity
{
    public string Email { get; set; }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            catalog_services = root / "src" / "Libraries" / "Nop.Services" / "Catalog"
            catalog_services.mkdir(parents=True)
            (catalog_services / "IProductService.cs").write_text(
                "public interface IProductService { }\n",
                encoding="utf-8",
            )
            (catalog_services / "ProductService.cs").write_text(
                "public class ProductService : IProductService { }\n",
                encoding="utf-8",
            )
            caching_services = root / "src" / "Libraries" / "Nop.Services" / "Caching"
            caching_services.mkdir(parents=True)
            (caching_services / "IStaticCacheManager.cs").write_text(
                "public interface IStaticCacheManager { }\n",
                encoding="utf-8",
            )
            data_library = root / "src" / "Libraries" / "Nop.Data"
            data_library.mkdir(parents=True)
            (data_library / "EntityRepository.cs").write_text(
                "public class EntityRepository<TEntity> where TEntity : BaseEntity { }\n",
                encoding="utf-8",
            )
            service_tests = root / "src" / "Tests" / "Nop.Tests" / "Nop.Services.Tests" / "Catalog"
            service_tests.mkdir(parents=True)
            (service_tests / "ProductServiceTests.cs").write_text(
                """
using Nop.Services.Catalog;

public class ProductServiceTests
{
    private IProductService _productService;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            data_tests = root / "src" / "Tests" / "Nop.Tests" / "Nop.Data.Tests"
            data_tests.mkdir(parents=True)
            (data_tests / "EntityRepositoryTests.cs").write_text(
                "public class EntityRepositoryTests { private IStaticCacheManager _cache; private EntityRepository<Product> _repository; }\n",
                encoding="utf-8",
            )
            domain_tests = root / "src" / "Tests" / "Nop.Tests" / "Nop.Core.Tests" / "Domain" / "Common"
            domain_tests.mkdir(parents=True)
            (domain_tests / "AddressValueTests.cs").write_text(
                "public class AddressValueTests { public void CanCloneAddress() { var address = new Address(); } }\n",
                encoding="utf-8",
            )
            ansible_inventory = root / "deploy" / "inventory"
            ansible_inventory.mkdir(parents=True)
            (ansible_inventory / "hosts").write_text(
                "[web]\nshop ansible_host=127.0.0.1\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            routes = {(route.kind, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("aspnetcore-map-controller-route", "ANY", "/{lang}/login", "Customer#Login"), routes)
            self.assertIn(("aspnetcore-map-controller-route", "ANY", "/cart/estimateshipping", "ShoppingCart#GetEstimateShipping"), routes)
            self.assertIn(("aspnetcore-map-dynamic-controller-route", "ANY", "/{lang}/{catalogSeName}/{seName}", "SlugRouteTransformer"), routes)
            self.assertIn(("aspnetcore-map-controller-route", "ANY", "/{lang}/{seName}", "Product#ProductDetails"), routes)
            self.assertIn(("aspnetcore-map-controller-route", "ANY", "/{lang}/{seName}", "Catalog#Category"), routes)
            self.assertIn(("aspnetcore-map-controller-route", "ANY", "/{lang}/{seName}", "News#NewsItem"), routes)
            self.assertIn(("aspnetcore-map-controller-route", "ANY", "/Plugins/FacebookPixel/Configure", "FacebookPixel#Configure"), routes)
            self.assertIn(("aspnetcore-conventional-action", "POST", "/Admin/Product/ProductList", "ProductList"), routes)
            self.assertIn(("aspnetcore-conventional-action", "POST", "/Admin/FacebookPixel/Configure", "Configure"), routes)
            self.assertNotIn(("aspnetcore-route", "POST", "/", "ProductList"), routes)
            slug_route = next(
                route
                for route in facts.api_routes
                if route.kind == "aspnetcore-map-dynamic-controller-route"
                and route.path == "/{lang}/{catalogSeName}/{seName}"
            )
            self.assertEqual(["lang", "catalogSeName", "seName"], [param.name for param in slug_route.parameters])
            ansible_facts = [fact for fact in facts.runtime_configs if fact.kind.startswith("ansible")]
            self.assertTrue(any(fact.path == "deploy/inventory/hosts" for fact in ansible_facts))
            self.assertFalse(any(fact.path.endswith("InventoryApiRequest.cs") for fact in ansible_facts))
            service_names = {service.name for service in facts.services}
            repository_names = {repository.name for repository in facts.repositories}
            self.assertIn("ProductService", service_names)
            self.assertIn("IProductService", service_names)
            self.assertIn("EntityRepository", repository_names)
            test_maps = {item.test_path: item for item in facts.test_maps}
            self.assertEqual(
                "service",
                test_maps[
                    "src/Tests/Nop.Tests/Nop.Services.Tests/Catalog/ProductServiceTests.cs"
                ].target_kind,
            )
            self.assertIn(
                test_maps[
                    "src/Tests/Nop.Tests/Nop.Services.Tests/Catalog/ProductServiceTests.cs"
                ].target,
                {"ProductService", "IProductService"},
            )
            self.assertEqual(
                "repository",
                test_maps["src/Tests/Nop.Tests/Nop.Data.Tests/EntityRepositoryTests.cs"].target_kind,
            )
            self.assertEqual(
                "EntityRepository",
                test_maps["src/Tests/Nop.Tests/Nop.Data.Tests/EntityRepositoryTests.cs"].target,
            )
            self.assertEqual(
                "data-model",
                test_maps[
                    "src/Tests/Nop.Tests/Nop.Core.Tests/Domain/Common/AddressValueTests.cs"
                ].target_kind,
            )
            self.assertEqual(
                "Address",
                test_maps[
                    "src/Tests/Nop.Tests/Nop.Core.Tests/Domain/Common/AddressValueTests.cs"
                ].target,
            )


if __name__ == "__main__":
    unittest.main()
