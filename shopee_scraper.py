#!/usr/bin/env python3
"""DiskPrices Singapore — Shopee.sg search via ZenRows (public search JSON).

Primary SEA path after BuyWhere / official affiliate APIs stalled.
Requires ZENROWS_API_KEY (same secret as Amazon). Soft-fails by default
(SEA_SOFT_FAIL=1) so a Shopee outage does not block Amazon export.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any
from urllib.parse import quote_plus, urlencode

import requests

from scrape_common import (
    STORAGE_QUERIES,
    init_db,
    process_products,
    save_products,
    sea_soft_exit,
    using_proxy,
    zenrows_get,
)

PLATFORM = "Shopee"
SEARCH_BASE = "https://shopee.sg/api/v4/search/search_items"
PRICE_DIVISOR = 100_000  # Shopee micros → SGD
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-SG,en;q=0.9",
    "Referer": "https://shopee.sg/",
    "X-Requested-With": "XMLHttpRequest",
}


def require_zenrows() -> None:
    if not os.environ.get("ZENROWS_API_KEY", "").strip():
        sea_soft_exit(
            "ZENROWS_API_KEY is not set — refusing unofficial Shopee scrape without proxy. "
            "Add the same GitHub secret used by Amazon."
        )


def _slugify(title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE)
    slug = re.sub(r"[\s_]+", "-", slug.strip()).strip("-")
    return slug[:80] or "item"


def _price_sgd(*candidates: Any) -> float:
    for raw in candidates:
        if raw is None or raw == "":
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        if val <= 0:
            continue
        # Micros (×100000) for typical SG listings; already-decimal fallback.
        if val >= 1000:
            val = val / PRICE_DIVISOR
        if 0 < val < 50_000:
            return val
    return 0.0


def _image_url(image_key: str) -> str:
    key = (image_key or "").strip()
    if not key:
        return ""
    if key.startswith("http"):
        return key
    return f"https://down-sg.img.susercontent.com/file/{key}"


def _product_url(shopid: Any, itemid: Any, title: str) -> str:
    if shopid is None or itemid is None:
        return ""
    return f"https://shopee.sg/{_slugify(title)}-i.{shopid}.{itemid}"


def _normalize_item(entry: dict) -> dict | None:
    basic = entry.get("item_basic") if isinstance(entry.get("item_basic"), dict) else entry
    if not isinstance(basic, dict):
        return None
    title = (basic.get("name") or "").strip()
    itemid = basic.get("itemid") or basic.get("item_id") or entry.get("itemid")
    shopid = basic.get("shopid") or basic.get("shop_id") or entry.get("shopid")
    url = _product_url(shopid, itemid, title)
    price = _price_sgd(
        basic.get("price_min"),
        basic.get("price"),
        basic.get("price_max"),
    )
    if not title or not url or price <= 0:
        return None
    return {
        "title": title,
        "url": url,
        "image_url": _image_url(basic.get("image") or ""),
        "price": price,
        "original_price": price,
        "platform": PLATFORM,
        "seller": (basic.get("shop_name") or PLATFORM).strip() or PLATFORM,
    }


def search_items(session: requests.Session, keyword: str, newest: int = 0, limit: int = 60) -> list[dict]:
    params = {
        "keyword": keyword,
        "limit": limit,
        "newest": newest,
        "by": "relevancy",
        "order": "desc",
        "page_type": "search",
        "scenario": "PAGE_GLOBAL_SEARCH",
        "version": 2,
    }
    url = f"{SEARCH_BASE}?{urlencode(params, quote_via=quote_plus)}"
    resp = zenrows_get(session, url, headers=HEADERS, timeout=60)
    if resp is None:
        print(f"  no response for '{keyword}' newest={newest}")
        return []
    if resp.status_code != 200:
        print(f"  HTTP {resp.status_code} for '{keyword}' newest={newest}: {resp.text[:200]}")
        return []
    try:
        data = resp.json()
    except ValueError:
        # ZenRows may return HTML challenge pages
        snippet = resp.text[:120].replace("\n", " ")
        print(f"  Non-JSON for '{keyword}': {snippet}")
        return []
    items = data.get("items")
    if items is None and isinstance(data.get("data"), dict):
        items = data["data"].get("items")
    if not isinstance(items, list):
        err = data.get("error") or data.get("error_msg") or data.get("message")
        print(f"  empty/malformed items for '{keyword}' (error={err})")
        return []
    out: list[dict] = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        norm = _normalize_item(entry)
        if norm:
            out.append(norm)
    return out


def main() -> None:
    require_zenrows()
    init_db()
    session = requests.Session()
    print(f"Proxy API: {'yes' if using_proxy() else 'no'}")

    all_products: list[dict] = []
    empty_streak = 0
    for q in STORAGE_QUERIES:
        print(f"Shopee ZenRows: {q}")
        page_products: list[dict] = []
        for newest in (0, 60):
            items = search_items(session, q, newest=newest, limit=60)
            products = process_products(items, default_platform=PLATFORM, default_seller=PLATFORM)
            page_products.extend(products)
            all_products.extend(products)
            time.sleep(0.6)
        print(f"  Total: {len(page_products)}")
        if len(page_products) == 0:
            empty_streak += 1
            if empty_streak >= 5 and not all_products:
                print("Fail-fast: first 5 queries returned 0 products.")
                break
        else:
            empty_streak = 0

    deduped: dict[str, dict] = {}
    for p in all_products:
        deduped.setdefault(p["url"], p)
    all_products = list(deduped.values())
    all_products.sort(key=lambda p: (p["capacity_tb"] >= 1, -p["capacity_tb"]), reverse=True)

    print(f"\n=== Shopee ZenRows grand total: {len(all_products)} ===")
    if len(all_products) == 0:
        sea_soft_exit("Shopee ZenRows scrape returned 0 storage products — fail-closed (soft).")

    save_products(all_products)
    print(f"Saved {len(all_products)} Shopee products.")


if __name__ == "__main__":
    main()
