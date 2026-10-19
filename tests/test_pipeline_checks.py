#!/usr/bin/env python3
import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline_checks import is_meaningful_change, staleness_hours


class TestMeaningfulDiff(unittest.TestCase):
    base = {"products": [{"url": "u", "price": 1.0}], "lastUpdated": "2026-09-19T09:41:39", "exportedAt": "a"}

    def test_exported_at_only_is_not_meaningful(self):
        self.assertFalse(is_meaningful_change(self.base, {**self.base, "exportedAt": "b"}))

    def test_product_change_is_meaningful(self):
        new = {**self.base, "products": [{"url": "u", "price": 2.0}], "exportedAt": "b"}
        self.assertTrue(is_meaningful_change(self.base, new))

    def test_last_updated_change_is_meaningful(self):
        self.assertTrue(is_meaningful_change(self.base, {**self.base, "lastUpdated": "2026-10-19T00:00:00"}))


class TestStaleness(unittest.TestCase):
    now = datetime(2026, 10, 19, 0, 0, tzinfo=timezone.utc)

    def test_naive_treated_as_utc(self):
        age = staleness_hours({"lastUpdated": "2026-10-17T00:00:00"}, now=self.now)
        self.assertAlmostEqual(age, 48.0)

    def test_falls_back_to_product_timestamps(self):
        doc = {"products": [{"timestamp": "2026-10-18T12:00:00"}, {"timestamp": "2026-10-10T00:00:00"}]}
        self.assertAlmostEqual(staleness_hours(doc, now=self.now), 12.0)

    def test_unknown(self):
        self.assertIsNone(staleness_hours({"products": []}, now=self.now))


if __name__ == "__main__":
    unittest.main()
