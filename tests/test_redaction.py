#!/usr/bin/env python3
"""Regression: secrets in proxy URLs/exceptions are redacted before logging."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scrape_common  # noqa: E402


class TestRedaction(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)
        os.environ["ZENROWS_API_KEY"] = "ZENROWS_TEST_SECRET_1234567890"
        os.environ["APIFY_TOKEN"] = "APIFY_TEST_TOKEN_0987654321"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_redact_secrets_replaces_values(self):
        msg = (
            "HTTPSConnectionPool(host='api.zenrows.com', port=443): Max retries "
            "exceeded with url: https://api.zenrows.com/v1/"
            "?apikey=ZENROWS_TEST_SECRET_1234567890&url=https%3A%2F%2Fwww.amazon.sg"
        )
        out = scrape_common.redact_secrets(msg)
        self.assertNotIn("ZENROWS_TEST_SECRET_1234567890", out)
        self.assertIn(scrape_common.REDACTED, out)
        self.assertIn("api.zenrows.com", out)

    def test_redact_url_strips_credentials(self):
        url = (
            "https://api.zenrows.com/v1/?apikey=ZENROWS_TEST_SECRET_1234567890"
            "&url=https%3A%2F%2Fwww.amazon.sg%2Fs"
        )
        out = scrape_common.redact_url(url)
        self.assertNotIn("ZENROWS_TEST_SECRET_1234567890", out)
        self.assertIn("url=https", out)

    def test_redact_url_keeps_clean_url(self):
        url = "https://www.amazon.sg/s?k=ssd"
        self.assertEqual(scrape_common.redact_url(url), url)

    def test_noop_when_no_secrets(self):
        self.assertEqual(scrape_common.redact_secrets("plain text"), "plain text")
        self.assertEqual(scrape_common.redact_secrets(None), None)

    def test_scraperapi_uses_https(self):
        os.environ["SCRAPERAPI_KEY"] = "SCRAPER_TEST_KEY_1234567890"
        out = scrape_common.proxied_url("https://www.amazon.sg/s?k=ssd")
        self.assertTrue(out.startswith("https://api.scraperapi.com?"))
        self.assertNotIn("http://api.scraperapi.com", out)


if __name__ == "__main__":
    unittest.main()
