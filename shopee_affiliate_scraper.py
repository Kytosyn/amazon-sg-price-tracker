#!/usr/bin/env python3
"""DiskPrices Singapore — official Shopee Affiliate Open API (GraphQL) importer.

Endpoint (SG): https://open-api.affiliate.shopee.com.sg/graphql
Auth header:  SHA256 Credential={appId},Timestamp={ts},Signature={sha256(appId+ts+body+secret)}
Env:          SHOPEE_AFFILIATE_APP_ID, SHOPEE_AFFILIATE_SECRET

Signup / Open API credentials: https://affiliate.shopee.sg/
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from typing import Any

import requests

from scrape_common import STORAGE_QUERIES, init_db, process_products, save_products

GRAPHQL_URL = "https://open-api.affiliate.shopee.com.sg/graphql"
SIGNUP_URL = "https://affiliate.shopee.sg/"
PLATFORM = "Shopee"

# GraphQL fields used for DiskPrices mapping.
PRODUCT_OFFER_QUERY = """
query ProductOffer($keyword: String!, $page: Int!, $limit: Int!) {
  productOfferV2(keyword: $keyword, listType: 0, sortType: 4, page: $page, limit: $limit) {
    nodes {
      itemId
      productName
      productLink
      offerLink
      imageUrl
      priceMin
      priceMax
      shopId
      shopName
    }
    pageInfo {
      page
      limit
      hasNextPage
    }
  }
}
""".strip()


def require_credentials() -> tuple[str, str]:
    app_id = os.environ.get("SHOPEE_AFFILIATE_APP_ID", "").strip()
    secret = os.environ.get("SHOPEE_AFFILIATE_SECRET", "").strip()
    if not app_id or not secret:
        print("ERROR: Shopee Affiliate credentials are not set.")
        print("Export both env vars (or add GitHub Actions secrets with the same names):")
        print("  SHOPEE_AFFILIATE_APP_ID")
        print("  SHOPEE_AFFILIATE_SECRET")
        print(f"Sign up / get App ID + Secret: {SIGNUP_URL}")
        print("See docs/AFFILIATE_SETUP.md for step-by-step SG setup.")
        sys.exit(1)
    return app_id, secret


def _sign(app_id: str, secret: str, body: str, timestamp: str) -> str:
    """SHA256(appId + timestamp + requestBody + secret) hex digest."""
    factor = f"{app_id}{timestamp}{body}{secret}"
    return hashlib.sha256(factor.encode("utf-8")).hexdigest()


def _auth_header(app_id: str, secret: str, body: str) -> dict[str, str]:
    ts = str(int(time.time()))
    sig = _sign(app_id, secret, body, ts)
    return {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": (
            f"SHA256 Credential={app_id},Timestamp={ts},Signature={sig}"
        ),
    }


def _parse_price(*candidates: Any) -> float:
    """Parse affiliate price fields (strings in local currency, or scaled ints)."""
    for raw in candidates:
        if raw is None or raw == "":
            continue
        if isinstance(raw, (int, float)):
            val = float(raw)
        else:
            text = str(raw).strip().replace(",", "")
            text = re.sub(r"[^\d.]", "", text)
            if not text:
                continue
            try:
                val = float(text)
            except ValueError:
                continue
        # Affiliate GraphQL usually returns SGD as a decimal string ("89.90").
        # Some regional backends return micro-units; clamp absurd HDD/SSD prices.
        if val > 1_000_000:
            val = val / 100_000
        elif val > 50_000:
            val = val / 100
        if val > 0:
            return val
    return 0.0


def _normalize_node(node: dict) -> dict | None:
    title = (node.get("productName") or "").strip()
    url = (node.get("offerLink") or node.get("productLink") or "").strip()
    if not title or not url:
        return None
    price = _parse_price(node.get("priceMin"), node.get("priceMax"))
    if price <= 0:
        return None
    seller = (node.get("shopName") or PLATFORM).strip() or PLATFORM
    return {
        "title": title,
        "url": url,
        "image_url": (node.get("imageUrl") or "").strip(),
        "price": price,
        "original_price": price,
        "platform": PLATFORM,
        "seller": seller,
    }


def graphql_product_offer(
    session: requests.Session,
    app_id: str,
    secret: str,
    keyword: str,
    page: int = 1,
    limit: int = 50,
) -> list[dict]:
    """Call productOfferV2. Body bytes signed must match the POST body exactly."""
    payload = {
        "query": PRODUCT_OFFER_QUERY,
        "variables": {"keyword": keyword, "page": page, "limit": limit},
    }
    # Compact JSON so the signed string matches what we transmit.
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    headers = _auth_header(app_id, secret, body)
    resp = session.post(GRAPHQL_URL, data=body.encode("utf-8"), headers=headers, timeout=40)
    if resp.status_code != 200:
        print(f"  HTTP {resp.status_code} for '{keyword}' page {page}: {resp.text[:300]}")
        return []
    try:
        data = resp.json()
    except ValueError:
        print(f"  Non-JSON response for '{keyword}' page {page}")
        return []
    if data.get("errors"):
        print(f"  GraphQL errors for '{keyword}' page {page}: {data['errors']}")
        return []
    connection = (data.get("data") or {}).get("productOfferV2") or {}
    nodes = connection.get("nodes") or []
    items: list[dict] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        norm = _normalize_node(node)
        if norm:
            items.append(norm)
    return items


def main() -> None:
    app_id, secret = require_credentials()
    init_db()
    session = requests.Session()

    all_products: list[dict] = []
    for q in STORAGE_QUERIES:
        print(f"Shopee Affiliate: {q}")
        page_products: list[dict] = []
        for page in (1, 2):
            items = graphql_product_offer(session, app_id, secret, q, page=page, limit=50)
            products = process_products(items, default_platform=PLATFORM, default_seller=PLATFORM)
            page_products.extend(products)
            all_products.extend(products)
            time.sleep(0.4)
        print(f"  Total: {len(page_products)}")

    deduped: dict[str, dict] = {}
    for p in all_products:
        deduped.setdefault(p["url"], p)
    all_products = list(deduped.values())
    all_products.sort(key=lambda p: (p["capacity_tb"] >= 1, -p["capacity_tb"]), reverse=True)

    print(f"\n=== Shopee grand total: {len(all_products)} ===")
    if len(all_products) == 0:
        print("ERROR: Shopee Affiliate returned 0 storage products — fail-closed.")
        print("Check App ID/Secret, Open API access approval, and query results in the portal.")
        print(f"Portal: {SIGNUP_URL}")
        sys.exit(1)

    save_products(all_products)
    print(f"Saved {len(all_products)} Shopee products.")


if __name__ == "__main__":
    main()
