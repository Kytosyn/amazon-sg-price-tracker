#!/usr/bin/env python3
"""Regression: init_db migrates old products schema; save_products self-heals."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scrape_common  # noqa: E402
from scrape_common import (  # noqa: E402
    ABSURD_MIN_CAPACITY_TB,
    ABSURD_MIN_COST_PER_TB_SGD,
    init_db,
    process_products,
    save_products,
)


OLD_SCHEMA_SQL = """
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    image_url TEXT,
    price REAL NOT NULL,
    original_price REAL,
    capacity_gb REAL NOT NULL,
    capacity_tb REAL NOT NULL,
    is_ssd BOOLEAN NOT NULL,
    cost_per_tb REAL NOT NULL,
    rating REAL DEFAULT 0,
    review_count INTEGER DEFAULT 0,
    seller TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


class TestInitDbMigrate(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.db = os.path.join(self._td.name, "diskprices.db")
        self._prev = scrape_common.DB_PATH
        scrape_common.DB_PATH = self.db

    def tearDown(self):
        scrape_common.DB_PATH = self._prev
        self._td.cleanup()

    def _make_old_db(self):
        conn = sqlite3.connect(self.db)
        conn.execute(OLD_SCHEMA_SQL)
        conn.execute(
            """INSERT INTO products
               (platform,title,url,image_url,price,original_price,
                capacity_gb,capacity_tb,is_ssd,cost_per_tb,seller)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "Amazon.sg",
                "WD 8TB Elements Desktop External Hard Drive USB 3.0",
                "https://www.amazon.sg/dp/B0OLDTEST01",
                "",
                200.0,
                200.0,
                8000.0,
                8.0,
                0,
                25.0,
                "Amazon.sg",
            ),
        )
        conn.commit()
        conn.close()

    def test_init_db_adds_missing_columns(self):
        self._make_old_db()
        cols_before = {
            r[1] for r in sqlite3.connect(self.db).execute("PRAGMA table_info(products)")
        }
        self.assertNotIn("first_seen", cols_before)
        self.assertNotIn("last_seen", cols_before)
        self.assertNotIn("is_active", cols_before)

        init_db()

        cols = {
            r[1] for r in sqlite3.connect(self.db).execute("PRAGMA table_info(products)")
        }
        for name in ("first_seen", "last_seen", "is_active"):
            self.assertIn(name, cols)

    def test_save_products_on_old_schema_without_prior_init(self):
        """Mirrors Actions failure: INSERT first_seen on unmigrated diskprices.db."""
        self._make_old_db()
        # Deliberately skip caller init_db — save_products must migrate itself.
        products = [
            {
                "platform": "Amazon.sg",
                "title": "Seagate IronWolf 4TB Internal NAS HDD",
                "url": "https://www.amazon.sg/dp/B0NEWTEST01",
                "image_url": "",
                "price": 140.0,
                "original_price": 140.0,
                "capacity_gb": 4000.0,
                "capacity_tb": 4.0,
                "is_ssd": False,
                "cost_per_tb": 35.0,
                "seller": "Amazon.sg",
            }
        ]
        save_products(products)
        conn = sqlite3.connect(self.db)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(products)")}
        self.assertIn("first_seen", cols)
        n = conn.execute(
            "SELECT COUNT(*) FROM products WHERE url LIKE '%B0NEWTEST01'"
        ).fetchone()[0]
        self.assertEqual(n, 1)
        conn.close()

    def test_absurd_cost_per_tb_rejects_fake_high_tb(self):
        # 24TB @ S$30 → S$1.25/TB — typical empty-enclosure / fake listing
        items = [
            {
                "title": "Generic 24TB Internal Hard Drive NAS Enterprise",
                "url": "https://www.amazon.sg/dp/B0FAKE24TB",
                "price": 30.0,
                "image_url": "",
            },
            {
                # Real-ish enterprise floor well above S$4/TB
                "title": "Seagate Exos 20TB Enterprise Internal Hard Drive",
                "url": "https://www.amazon.sg/dp/B0REAL20TB",
                "price": 400.0,  # S$20/TB
                "image_url": "",
            },
        ]
        out = process_products(items)
        urls = {p["url"] for p in out}
        self.assertNotIn("https://www.amazon.sg/dp/B0FAKE24TB", urls)
        self.assertIn("https://www.amazon.sg/dp/B0REAL20TB", urls)
        self.assertGreaterEqual(ABSURD_MIN_CAPACITY_TB, 4.0)
        self.assertGreaterEqual(ABSURD_MIN_COST_PER_TB_SGD, 4.0)


if __name__ == "__main__":
    unittest.main()
