#!/usr/bin/env python3
"""Regression: ADMIN_API_KEY gates state-changing endpoints and fails closed."""

from __future__ import annotations

import importlib
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import auth as admin_auth  # noqa: E402


class TestAdminAuth(unittest.TestCase):
    def _reload(self, value):
        old = os.environ.get("ADMIN_API_KEY")
        if value is None:
            os.environ.pop("ADMIN_API_KEY", None)
        else:
            os.environ["ADMIN_API_KEY"] = value
        try:
            return importlib.reload(admin_auth)
        finally:
            if old is None:
                os.environ.pop("ADMIN_API_KEY", None)
            else:
                os.environ["ADMIN_API_KEY"] = old

    def test_unconfigured_fails_closed(self):
        m = self._reload(None)
        self.assertFalse(m.is_configured())
        self.assertFalse(m.is_valid_admin_key("anything"))
        self.assertFalse(m.is_valid_admin_key(None))
        self.assertFalse(m.is_valid_admin_key(""))

    def test_configured_accepts_only_exact_match(self):
        m = self._reload("test-admin-key-123")
        self.assertTrue(m.is_configured())
        self.assertTrue(m.is_valid_admin_key("test-admin-key-123"))
        self.assertFalse(m.is_valid_admin_key("wrong"))
        self.assertFalse(m.is_valid_admin_key("test-admin-key-12"))  # prefix
        self.assertFalse(m.is_valid_admin_key(""))
        self.assertFalse(m.is_valid_admin_key(None))


if __name__ == "__main__":
    unittest.main()
