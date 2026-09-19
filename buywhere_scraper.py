#!/usr/bin/env python3
"""DiskPrices Singapore - BuyWhere multi-platform importer (Shopee / Lazada / Amazon.sg / others).

Reads BUYWHERE_API_KEY from the environment. Exits 1 with a clear message if missing
or if zero storage products are found after all queries.
"""

import os
import sys
import time
import requests
from collections import Counter

from scrape_common import init_db, process_products, save_products

API_URL = "https://api.buywhere.ai/v1/products/search"

# HDD/SSD-focused subset (shorter than Amazon list to stay under free-tier quotas)
QUERIES = [
    "internal hard drive",
    "internal hdd",
    "external hard drive",
    "portable hard drive",
    "nas hard drive",
    "wd red",
    "wd gold",
    "seagate ironwolf",
    "seagate barracuda",
    "toshiba n300",
    "internal ssd",
    "nvme ssd",
    "m.2 ssd",
    "sata ssd",
    "external ssd",
    "portable ssd",
    "samsung 990",
    "samsung t7",
    "crucial mx500",
]


def require_api_key() -> str:
    key = os.environ.get("BUYWHERE_API_KEY", "").strip()
    if not key:
        print("ERROR: BUYWHERE_API_KEY is not set.")
        print("Add the secret in GitHub Actions (repo Settings → Secrets) or export it locally:")
        print("  export BUYWHERE_API_KEY=bw_live_...")
        print("Docs: https://buywhere.ai/quickstart")
        sys.exit(1)
    return key


def map_platform(merchant: str, url: str = "") -> str:
    """Map BuyWhere merchant/domain to UI platform labels."""
    blob = f"{merchant or ''} {url or ''}".lower()
    if "shopee" in blob:
        return "Shopee"
    if "lazada" in blob:
        return "Lazada"
    if "amazon" in blob:
        return "Amazon.sg"
    # Readable fallback so the UI gray badge still shows a name
    name = (merchant or "").strip()
    if not name:
        return "Other"
    # Prefer hostname-ish first segment without TLD clutter
    # e.g. "courts.com.sg" -> "Courts", "amazon.sg" already handled
    host = name.split("/")[0]
    label = host.split(".")[0] if "." in host else host
    return label.title() if label else "Other"


def _extract_price(raw) -> float:
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, dict):
        amount = raw.get("amount")
        if amount is None:
            amount = raw.get("value")
        try:
            return float(amount or 0)
        except (TypeError, ValueError):
            return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _normalize_item(raw: dict) -> dict | None:
    title = (raw.get("title") or raw.get("name") or "").strip()
    url = (raw.get("url") or "").strip()
    if not title or not url:
        return None
    price = _extract_price(raw.get("price"))
    original = _extract_price(raw.get("original_price") or raw.get("compare_at_price"))
    merchant = (raw.get("merchant") or raw.get("domain") or raw.get("source") or "").strip()
    platform = map_platform(merchant, url)
    return {
        "title": title,
        "url": url,
        "image_url": raw.get("image_url") or "",
        "price": price,
        "original_price": original if original > 0 else price,
        "platform": platform,
        "seller": merchant or platform,
    }


def search_products(session: requests.Session, api_key: str, query: str, limit: int = 50) -> list[dict]:
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    params = {
        "q": query,
        "country_code": "SG",
        "deliver_to": "SG",
        "limit": limit,
        "sort": "price_asc",
    }
    try:
        resp = session.get(API_URL, headers=headers, params=params, timeout=40)
    except requests.RequestException as e:
        print(f"  request error: {e}")
        return []

    if resp.status_code == 401:
        print("ERROR: BuyWhere returned 401 Unauthorized — check BUYWHERE_API_KEY.")
        sys.exit(1)
    if resp.status_code == 429:
        print(f"  rate limited on '{query}'; sleeping then skipping")
        time.sleep(5)
        return []
    if resp.status_code != 200:
        print(f"  HTTP {resp.status_code} on '{query}': {resp.text[:200]}")
        return []

    try:
        payload = resp.json()
    except ValueError:
        print(f"  invalid JSON on '{query}'")
        return []

    rows = payload.get("results") or payload.get("data") or []
    items = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = _normalize_item(row)
        if item:
            items.append(item)
    return items


def main():
    api_key = require_api_key()
    init_db()
    session = requests.Session()

    all_products = []
    for q in QUERIES:
        print(f"BuyWhere: {q}")
        items = search_products(session, api_key, q)
        products = process_products(items)
        print(f"  raw={len(items)} storage={len(products)}")
        all_products.extend(products)
        time.sleep(0.4)  # gentle pacing for free tier

    deduped = {}
    for p in all_products:
        deduped.setdefault(p["url"], p)
    all_products = list(deduped.values())
    all_products.sort(key=lambda p: (p["capacity_tb"] >= 1, -p["capacity_tb"]), reverse=True)

    counts = Counter(p["platform"] for p in all_products)
    print("\n=== BuyWhere platform counts ===")
    for platform, n in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
        print(f"  {platform}: {n}")
    print(f"=== Grand total: {len(all_products)} ===")

    if len(all_products) == 0:
        print("ERROR: BuyWhere returned 0 storage products — refusing empty write.")
        print("Hint: verify BUYWHERE_API_KEY and try a manual query against api.buywhere.ai")
        sys.exit(1)

    save_products(all_products)
    print(f"Saved {len(all_products)} products to diskprices.db")


if __name__ == "__main__":
    main()
