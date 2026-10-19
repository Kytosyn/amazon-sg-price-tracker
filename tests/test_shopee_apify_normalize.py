#!/usr/bin/env python3
"""Dry checks for Shopee Apify normalize + status constants."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shopee_scraper import (
    APIFY_SUCCESS_STATUSES,
    APIFY_TERMINAL_STATUSES,
    apify_max_charge_usd,
    apify_per_term_items,
    normalize_apify_item,
)


class TestNormalizeApifyItem(unittest.TestCase):
    def test_cents_to_sgd(self):
        row = {
            "type": "product",
            "title": "WD 4TB My Passport External Hard Drive",
            "price": 12900,  # cents
            "originalPrice": 15900,
            "url": "https://shopee.sg/wd-4tb-i.123.456",
            "shopId": 123,
            "itemId": 456,
            "imageUrl": "https://down-sg.img.susercontent.com/file/abc",
        }
        got = normalize_apify_item(row)
        self.assertIsNotNone(got)
        assert got is not None
        self.assertEqual(got["price"], 129.0)
        self.assertEqual(got["original_price"], 159.0)
        self.assertEqual(got["platform"], "Shopee")
        self.assertIn("123", got["seller"])

    def test_skips_non_product(self):
        self.assertIsNone(normalize_apify_item({"type": "ad", "title": "x", "price": 100}))

    def test_builds_url_from_ids(self):
        row = {
            "title": "Samsung 990 PRO 2TB NVMe SSD",
            "price": 24999,
            "shopId": 1,
            "itemId": 2,
        }
        got = normalize_apify_item(row)
        self.assertIsNotNone(got)
        assert got is not None
        self.assertTrue(got["url"].startswith("https://shopee.sg/"))
        self.assertIn("i.1.2", got["url"])


class TestApifyInputMapping(unittest.TestCase):
    def test_per_term_split_never_exceeds_total(self):
        for total, terms in ((20, 19), (100, 19), (5, 19), (200, 19), (1, 1)):
            per, used = apify_per_term_items(total, terms)
            self.assertGreaterEqual(per, 1)
            self.assertLessEqual(per * used, max(total, used))
            self.assertLessEqual(used, terms)
        self.assertEqual(apify_per_term_items(20, 19), (1, 19))
        self.assertEqual(apify_per_term_items(100, 19), (5, 19))
        self.assertEqual(apify_per_term_items(5, 19), (1, 5))

    def test_max_charge_default_and_ceiling(self):
        os.environ.pop("APIFY_SHOPEE_MAX_CHARGE_USD", None)
        self.assertEqual(apify_max_charge_usd(), 0.50)
        os.environ["APIFY_SHOPEE_MAX_CHARGE_USD"] = "99"
        try:
            self.assertEqual(apify_max_charge_usd(), 2.00)
        finally:
            os.environ.pop("APIFY_SHOPEE_MAX_CHARGE_USD", None)


class TestNormalizeGuards(unittest.TestCase):
    base = {
        "type": "product",
        "title": "Seagate IronWolf 8TB NAS HDD",
        "price": 32900,
        "url": "https://shopee.sg/x-i.9.8",
        "shopId": 9,
        "itemId": 8,
    }

    def test_decimal_price_kept_as_sgd(self):
        got = normalize_apify_item({**self.base, "price": 290.29})
        assert got is not None
        self.assertAlmostEqual(got["price"], 290.29)

    def test_skips_partial_and_non_sg(self):
        self.assertIsNone(normalize_apify_item({**self.base, "partial": True}))
        self.assertIsNone(normalize_apify_item({**self.base, "country": "MY", "currency": "MYR"}))
        self.assertIsNotNone(normalize_apify_item({**self.base, "country": "SG", "currency": "SGD"}))

    def test_shop_name_preferred_for_seller(self):
        got = normalize_apify_item({**self.base, "shopName": "Seagate Official Store"})
        assert got is not None
        self.assertEqual(got["seller"], "Seagate Official Store")


class TestApifyStatusConstants(unittest.TestCase):
    def test_ready_running_not_terminal(self):
        self.assertNotIn("READY", APIFY_TERMINAL_STATUSES)
        self.assertNotIn("RUNNING", APIFY_TERMINAL_STATUSES)

    def test_success_is_succeeded(self):
        self.assertEqual(APIFY_SUCCESS_STATUSES, frozenset({"SUCCEEDED"}))
        self.assertIn("SUCCEEDED", APIFY_TERMINAL_STATUSES)
        for s in ("FAILED", "TIMED-OUT", "ABORTED"):
            self.assertIn(s, APIFY_TERMINAL_STATUSES)


if __name__ == "__main__":
    unittest.main()
