#!/usr/bin/env python3
"""DiskPrices Singapore — Lazada Affiliate Open Platform importer (stub).

Research notes (2026-09, public docs without affiliate-portal login)
--------------------------------------------------------------------
Official portals:
  - Affiliate signup (SG): https://www.lazada.sg/lazada-affiliate-program
  - Lazada Open Platform:  https://open.lazada.com/
  - Regional REST base (seller): https://api.lazada.sg/rest

What is publicly documented without login:
  - Seller Open Platform (LazOP) uses:
      app_key, app_secret, access_token, timestamp, sign_method=sha256,
      sign = HMAC-SHA256 over sorted params (see open.lazada.com signing docs).
  - Seller product APIs such as GET /products/get and SearchSPUs operate on the
    *seller's own catalog*, not the marketplace-wide affiliate product offer feed.
  - Third-party writeups mention a separate Affiliate API family (product search /
    feed, link generation, reporting) gated behind an approved Lazada Affiliate
    account — exact path names and request schemas are behind login on
    open.lazada.com / the affiliate portal and could not be confirmed from public
    pages alone.

Therefore this module is intentionally a stub: it does NOT fake HTML scraping.
Once Eddy has Affiliate Open API docs access, fill in ENDPOINT + signing below
and replace `main()` with a real product-search loop using STORAGE_QUERIES and
scrape_common.process_products / save_products (platform='Lazada').

Env (planned):
  LAZADA_AFFILIATE_APP_KEY
  LAZADA_AFFILIATE_APP_SECRET
  LAZADA_AFFILIATE_ACCESS_TOKEN   # if LazOP-style OAuth is required
"""

from __future__ import annotations

import os
import sys

from scrape_common import STORAGE_QUERIES, init_db  # noqa: F401 — kept for future impl

PLATFORM = "Lazada"
SIGNUP_URL = "https://www.lazada.sg/lazada-affiliate-program"
OPEN_PLATFORM_URL = "https://open.lazada.com/"
SELLER_REST_SG = "https://api.lazada.sg/rest"

# TODO(Eddy): set the confirmed Affiliate product-search path once docs are visible, e.g.:
#   ENDPOINT = "https://api.lazada.sg/rest/affiliate/product/search"
#   or GraphQL / feed URL from the Affiliate Open API console.
ENDPOINT: str | None = None


def require_credentials() -> dict[str, str]:
    app_key = os.environ.get("LAZADA_AFFILIATE_APP_KEY", "").strip()
    app_secret = os.environ.get("LAZADA_AFFILIATE_APP_SECRET", "").strip()
    access_token = os.environ.get("LAZADA_AFFILIATE_ACCESS_TOKEN", "").strip()
    if not app_key or not app_secret:
        print("ERROR: Lazada Affiliate credentials are not set.")
        print("Export (or add GitHub Actions secrets):")
        print("  LAZADA_AFFILIATE_APP_KEY")
        print("  LAZADA_AFFILIATE_APP_SECRET")
        print("  LAZADA_AFFILIATE_ACCESS_TOKEN  (if required by the Affiliate API)")
        print(f"Apply: {SIGNUP_URL}")
        print(f"Open Platform / API console: {OPEN_PLATFORM_URL}")
        print("See docs/AFFILIATE_SETUP.md for step-by-step SG setup.")
        sys.exit(1)
    return {
        "app_key": app_key,
        "app_secret": app_secret,
        "access_token": access_token,
    }


def _signing_notes() -> None:
    print("Expected LazOP-style signing (seller docs; affiliate may match):")
    print(f"  Base URL (SG seller REST): {SELLER_REST_SG}")
    print("  Common query params: app_key, timestamp (ms), sign_method=sha256,")
    print("    access_token (when required), plus API-specific params.")
    print("  sign = HMAC-SHA256(app_secret, api_path + sorted(key+value) concat)")
    print("  Docs (login may be required):")
    print("    https://open.lazada.com/apps/doc/doc?nodeId=10450&docId=108068")


def main() -> None:
    creds = require_credentials()
    init_db()
    _ = STORAGE_QUERIES  # reuse planned once ENDPOINT is set
    _ = creds

    print("ERROR: Lazada Affiliate product-search endpoint is not yet wired.")
    print("Official public product-search for affiliates could not be confirmed")
    print("without portal login — refusing to fake-scrape Lazada HTML.")
    print()
    print("Next steps for Eddy:")
    print(f"  1. Apply / wait for approval: {SIGNUP_URL}")
    print(f"  2. Open API console (after approval): {OPEN_PLATFORM_URL}")
    print("  3. Copy App Key / App Secret (and Access Token if shown)")
    print("     into GitHub secrets: LAZADA_AFFILIATE_APP_KEY,")
    print("     LAZADA_AFFILIATE_APP_SECRET, LAZADA_AFFILIATE_ACCESS_TOKEN")
    print("  4. Paste the documented product-search path + sample request into")
    print("     lazada_affiliate_scraper.py (set ENDPOINT, implement call + map")
    print(f"     results to platform='{PLATFORM}').")
    print()
    _signing_notes()
    if ENDPOINT is None:
        print("TODO: ENDPOINT is None — implement after docs access.")
    sys.exit(1)


if __name__ == "__main__":
    main()
