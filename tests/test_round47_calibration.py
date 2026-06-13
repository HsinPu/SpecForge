from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round47LoopBackCalibrationTests(unittest.TestCase):
    def test_loopback_routes_contracts_models_and_data_layer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text(
                '{"dependencies":{"@loopback/rest":"^12.0.0","@loopback/repository":"^5.0.0"}}\n',
                encoding="utf-8",
            )
            controllers = root / "src" / "controllers"
            models = root / "src" / "models"
            repositories = root / "src" / "repositories"
            datasources = root / "src" / "datasources"
            controllers.mkdir(parents=True)
            models.mkdir(parents=True)
            repositories.mkdir(parents=True)
            datasources.mkdir(parents=True)

            (controllers / "product.controller.ts").write_text(
                """
import {Count, CountSchema, Filter, repository, Where} from '@loopback/repository';
import {post, param, get, getModelSchemaRef, getWhereSchemaFor, requestBody} from '@loopback/rest';
import {authenticate} from '@loopback/authentication';
import {Product} from '../models';
import {ProductRepository} from '../repositories';

export class ProductController {
  constructor(
    @repository(ProductRepository)
    public productRepository: ProductRepository,
  ) {}

  @post('/products', {
    responses: {
      '200': {
        description: 'Product model instance',
        content: {'application/json': {schema: getModelSchemaRef(Product)}},
      },
    },
  })
  @authenticate('jwt')
  async create(
    @requestBody({
      content: {
        'application/json': {
          schema: getModelSchemaRef(Product, {exclude: ['productId']}),
        },
      },
    })
    product: Omit<Product, 'productId'>,
  ): Promise<Product> {
    return this.productRepository.create(product);
  }

  @get('/products/{id}', {
    responses: {
      '200': {
        description: 'Product model instance',
        content: {'application/json': {schema: getModelSchemaRef(Product)}},
      },
    },
  })
  async findById(
    @param.path.string('id') id: string,
    @param.query.object('where', getWhereSchemaFor(Product))
    where?: Where<Product>,
  ): Promise<Product> {
    return this.productRepository.findById(id, where);
  }

  @get('/products/count', {
    responses: {
      '200': {
        description: 'Product model count',
        content: {'application/json': {schema: CountSchema}},
      },
    },
  })
  async count(): Promise<Count> {
    return this.productRepository.count();
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (models / "product.model.ts").write_text(
                """
import {Entity, model, property} from '@loopback/repository';

@model()
export class Product extends Entity {
  @property({
    type: 'string',
    id: true,
    generated: true,
  })
  productId?: string;

  @property({
    type: 'string',
    required: true,
  })
  name: string;

  @property({
    type: 'number',
    required: true,
  })
  price: number;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (repositories / "product.repository.ts").write_text(
                """
import {inject} from '@loopback/core';
import {DefaultCrudRepository} from '@loopback/repository';
import {MongoDataSource} from '../datasources';
import {Product, ProductRelations} from '../models';

export class ProductRepository extends DefaultCrudRepository<
  Product,
  typeof Product.prototype.productId,
  ProductRelations
> {
  constructor(@inject('datasources.mongo') dataSource: MongoDataSource) {
    super(Product, dataSource);
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )
            (datasources / "mongo.datasource.ts").write_text(
                """
import {juggler} from '@loopback/repository';

const config = {
  name: 'mongo',
  connector: 'mongodb',
};

export class MongoDataSource extends juggler.DataSource {
  static dataSourceName = 'mongo';
  constructor() {
    super(config);
  }
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            facts = scan_project(root)

            frameworks = {framework.name for framework in facts.frameworks}
            self.assertIn("loopback", frameworks)
            self.assertIn("loopback-repository", frameworks)

            routes = {(route.framework, route.kind, route.method, route.path, route.handler) for route in facts.api_routes}
            self.assertIn(("loopback", "loopback-route", "POST", "/products", "create"), routes)
            self.assertIn(("loopback", "loopback-route", "GET", "/products/{id}", "findById"), routes)
            self.assertIn(("loopback", "loopback-route", "GET", "/products/count", "count"), routes)

            create_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "loopback" and contract.method == "POST" and contract.path == "/products"
            )
            self.assertIn("body:Omit<Product, 'productId'>", create_contract.request_hints)
            self.assertIn("body:requestBody", create_contract.request_hints)
            self.assertIn("body-schema:Product", create_contract.request_hints)
            self.assertIn("auth:jwt", create_contract.request_hints)
            self.assertIn("return:Promise<Product>", create_contract.response_hints)
            self.assertIn("response-schema:Product", create_contract.response_hints)
            self.assertIn("repository:productRepository.create", create_contract.response_hints)
            self.assertIn("200", create_contract.status_codes)

            find_contract = next(
                contract
                for contract in facts.api_contracts
                if contract.framework == "loopback" and contract.method == "GET" and contract.path == "/products/{id}"
            )
            self.assertIn("path:id:string", find_contract.request_hints)
            self.assertIn("query:where:object", find_contract.request_hints)
            self.assertIn("query-where:Product", find_contract.request_hints)
            self.assertIn("repository:productRepository.findById", find_contract.response_hints)

            models_by_name = {model.name: model for model in facts.data_models}
            self.assertIn("Product", models_by_name)
            self.assertEqual("loopback-model", models_by_name["Product"].kind)
            self.assertIn("productId:string", models_by_name["Product"].fields)
            self.assertIn("name:string", models_by_name["Product"].fields)
            self.assertIn("primary-key:productId", models_by_name["Product"].annotations)
            self.assertIn("required:name", models_by_name["Product"].annotations)

            data_layers = {(item.kind, item.name) for item in facts.data_layers}
            self.assertIn(("code-model:loopback-model", "Product"), data_layers)
            self.assertIn(("loopback-repository", "ProductRepository"), data_layers)
            self.assertIn(("loopback-datasource", "MongoDataSource"), data_layers)


if __name__ == "__main__":
    unittest.main()
