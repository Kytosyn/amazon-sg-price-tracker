#!/usr/bin/env python3
"""Dry checks for Shopee Apify normalize + status constants."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shopee_scraper import (
    APIFY_SUCCESS_STATUSES,
    APIFY_TERMINAL_STATUSES,
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
