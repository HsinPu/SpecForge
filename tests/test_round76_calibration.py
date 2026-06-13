from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from specforge.scanner import scan_project


class Round76WooCommerceCalibrationTests(unittest.TestCase):
    def test_woocommerce_data_models_and_wordpress_table_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "composer.json").write_text('{"require":{"johnpbloch/wordpress":"^6.0"}}\n', encoding="utf-8")
            includes = root / "plugins" / "woocommerce" / "includes"
            includes.mkdir(parents=True)

            (includes / "class-wc-order.php").write_text(
                """
<?php
class WC_Order extends WC_Abstract_Order {
    protected $object_type = 'order';
    protected $data_store_name = 'order';
    protected $data = array(
        'parent_id' => 0,
        'status' => '',
        'billing' => array(
            'first_name' => '',
        ),
        'total' => 0,
        'date_paid' => null,
    );
    protected $legacy_datastore_props = array(
        '_recorded_sales',
        '_download_permissions_granted',
    );
}
""".strip(),
                encoding="utf-8",
            )
            (includes / "class-wc-product-factory.php").write_text(
                "<?php\nclass WC_Product_Factory {}\n",
                encoding="utf-8",
            )
            (includes / "class-wc-product-data-store-cpt.php").write_text(
                "<?php\nclass WC_Product_Data_Store_CPT {}\n",
                encoding="utf-8",
            )
            (includes / "wc-update-functions.php").write_text(
                """
<?php
function wc_update_tables() {
    global $wpdb;
    dbDelta( "CREATE TABLE {$wpdb->prefix}woocommerce_order_items (
        order_item_id bigint(20) NOT NULL,
        order_id bigint(20) NOT NULL
    )" );
    $wpdb->query( "ALTER TABLE {$wpdb->prefix}wc_order_stats ADD INDEX order_id (order_id)" );
    $wpdb->get_var( "SHOW TABLES LIKE '{$wpdb->prefix}woocommerce_api_keys';" );
    $data_store = WC_Data_Store::load( 'order' );
}
""".strip(),
                encoding="utf-8",
            )

            facts = scan_project(root)

            models = {model.name: model for model in facts.data_models}
            self.assertIn("WC_Order", models)
            self.assertEqual("woocommerce-data-model", models["WC_Order"].kind)
            self.assertIn("parent_id:number", models["WC_Order"].fields)
            self.assertIn("status:string", models["WC_Order"].fields)
            self.assertIn("billing:array", models["WC_Order"].fields)
            self.assertIn("date_paid:null", models["WC_Order"].fields)
            self.assertIn("object-type:order", models["WC_Order"].annotations)
            self.assertIn("data-store-name:order", models["WC_Order"].annotations)
            self.assertIn("legacy-datastore-prop:_recorded_sales", models["WC_Order"].annotations)
            self.assertNotIn("WC_Product_Factory", models)
            self.assertNotIn("WC_Product_Data_Store_CPT", models)

            table_fact = next(item for item in facts.data_layers if item.kind == "wordpress-table-reference")
            self.assertIn("table:woocommerce_order_items", table_fact.details)
            self.assertIn("table:woocommerce_api_keys", table_fact.details)
            self.assertIn("alter:wc_order_stats", table_fact.details)
            self.assertIn("migration:dbDelta", table_fact.details)

            self.assertTrue(
                any("load:order" in item.details for item in facts.data_layers if item.kind == "woocommerce-data-store")
            )

            code_model_fact = next(
                item for item in facts.data_layers if item.kind == "code-model:woocommerce-data-model" and item.name == "WC_Order"
            )
            self.assertIn("data-store-name:order", code_model_fact.details)


if __name__ == "__main__":
    unittest.main()
