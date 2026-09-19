#!/usr/bin/env python3
"""DiskPrices Singapore — Shopee.sg search via ZenRows.

Primary SEA path after BuyWhere / official affiliate APIs stalled.
Requires ZENROWS_API_KEY (same secret as Amazon). Soft-fails by default
(SEA_SOFT_FAIL=1) so a Shopee outage does not block Amazon export.

Fetch strategy (post-#9 RESP001):
  Hitting ``/api/v4/search/search_items`` with ``mode=auto`` or direct
  ``js_render`` returned ZenRows RESP001. Prefer the public HTML search page
  with ``js_render`` + ``premium_proxy`` + ``json_response`` so ZenRows
  captures the browser's ``search_items`` XHR. Optional cheap API probe with
  premium_proxy only (no js_render) runs first.
"""

from __future__ import annotations

import json
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
    zenrows_quota_exceeded,
)

# Shorter list for ZenRows cost/latency (matches Lazada SEA_QUERIES).
SEA_QUERIES = [
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

PLATFORM = "Shopee"


class QuotaExceeded(RuntimeError):
    """ZenRows AUTH004 / HTTP 402."""

SEARCH_API = "https://shopee.sg/api/v4/search/search_items"
SEARCH_HTML = "https://shopee.sg/search"
PRICE_DIVISOR = 100_000  # Shopee micros → SGD

# Forwarded to the *target* via ZenRows ``custom_headers=true`` (not only the
# outer api.zenrows.com request). Keep Accept loose so HTML + JSON both work.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
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


def _items_from_search_payload(data: Any) -> list[dict]:
    """Normalize a Shopee search_items JSON body into product dicts."""
    if not isinstance(data, dict):
        return []
    items = data.get("items")
    if items is None and isinstance(data.get("data"), dict):
        items = data["data"].get("items")
    if not isinstance(items, list):
        return []
    out: list[dict] = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        norm = _normalize_item(entry)
        if norm:
            out.append(norm)
    return out


def _items_from_zenrows_json_response(payload: Any) -> list[dict]:
    """Pull search_items bodies out of ZenRows ``json_response`` XHR capture."""
    if not isinstance(payload, dict):
        return []
    # Direct search_items body (if somehow returned as top-level).
    direct = _items_from_search_payload(payload)
    if direct:
        return direct
    collected: list[dict] = []
    for req in payload.get("xhr") or []:
        if not isinstance(req, dict):
            continue
        url = str(req.get("url") or "")
        if "search_items" not in url and "/api/v4/search/" not in url:
            continue
        body = req.get("body")
        if body is None or body == "":
            continue
        if isinstance(body, (dict, list)):
            data = body
        else:
            try:
                data = json.loads(body)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        collected.extend(_items_from_search_payload(data))
    return collected


def _parse_response_items(resp: requests.Response, keyword: str, label: str) -> list[dict]:
    if zenrows_quota_exceeded(resp):
        print(f"  ZenRows quota exceeded ({label} HTTP {resp.status_code}): {resp.text[:200]}")
        raise QuotaExceeded("ZENROWS usage exceeded (AUTH004)")
    if resp.status_code != 200:
        print(f"  HTTP {resp.status_code} ({label}) for '{keyword}': {resp.text[:200]}")
        return []
    text = resp.text or ""
    try:
        data = resp.json()
    except ValueError:
        snippet = text[:120].replace("\n", " ")
        print(f"  Non-JSON ({label}) for '{keyword}': {snippet}")
        return []
    # ZenRows json_response wrapper → XHR search_items.
    from_xhr = _items_from_zenrows_json_response(data)
    if from_xhr:
        print(f"  {label}: {len(from_xhr)} items via json_response/XHR")
        return from_xhr
    # Plain search_items JSON (API probe path).
    plain = _items_from_search_payload(data)
    if plain:
        print(f"  {label}: {len(plain)} items via search JSON")
        return plain
    err = None
    if isinstance(data, dict):
        err = data.get("error") or data.get("error_msg") or data.get("message") or data.get("code")
    print(f"  empty/malformed ({label}) for '{keyword}' (error={err})")
    return []


def search_items(session: requests.Session, keyword: str, newest: int = 0, limit: int = 60) -> list[dict]:
    """Fetch Shopee results for one keyword.

    1) Cheap API probe: premium_proxy + proxy_country + custom_headers (no
       js_render / mode=auto — those hit RESP001 on this JSON endpoint).
    2) HTML search page with js_render + premium_proxy + wait + json_response
       to capture the browser's search_items XHR (RESP001 remedy path).
    """
    api_params = {
        "keyword": keyword,
        "limit": limit,
        "newest": newest,
        "by": "relevancy",
        "order": "desc",
        "page_type": "search",
        "scenario": "PAGE_GLOBAL_SEARCH",
        "version": 2,
    }
    api_url = f"{SEARCH_API}?{urlencode(api_params, quote_via=quote_plus)}"

    # --- Path A: API without js_render (may still REQS002; cheap to try) ---
    resp = zenrows_get(
        session,
        api_url,
        headers=HEADERS,
        timeout=90,
        retries=2,
        extra_params={
            "premium_proxy": "true",
            "proxy_country": "sg",
            "custom_headers": "true",
        },
    )
    if resp is not None:
        items = _parse_response_items(resp, keyword, "api/premium")
        if items:
            return items
        # REQS002 / RESP001 → fall through to HTML+js_render
        if resp.status_code in (400, 422) or "REQS002" in (resp.text or "") or "RESP001" in (resp.text or ""):
            print(f"  API probe blocked ({resp.status_code}); trying HTML+js_render+json_response")

    # --- Path B: HTML search + js_render + json_response (XHR capture) ---
    html_url = f"{SEARCH_HTML}?{urlencode({'keyword': keyword}, quote_via=quote_plus)}"
    resp = zenrows_get(
        session,
        html_url,
        headers=HEADERS,
        timeout=180,
        retries=2,
        extra_params={
            "js_render": "true",
            "premium_proxy": "true",
            "proxy_country": "sg",
            "wait": "5000",
            "json_response": "true",
            "custom_headers": "true",
        },
    )
    if resp is None:
        print(f"  no HTML response for '{keyword}'")
        return []
    return _parse_response_items(resp, keyword, "html/js_render")


def main() -> None:
    require_zenrows()
    init_db()
    session = requests.Session()
    print(f"Proxy API: {'yes' if using_proxy() else 'no'}")

    all_products: list[dict] = []
    empty_streak = 0
    queries = SEA_QUERIES or STORAGE_QUERIES
    try:
        for q in queries:
            print(f"Shopee ZenRows: {q}")
            page_products: list[dict] = []
            for newest in (0,):
                items = search_items(session, q, newest=newest, limit=60)
                products = process_products(items, default_platform=PLATFORM, default_seller=PLATFORM)
                page_products.extend(products)
                all_products.extend(products)
                time.sleep(0.8)
            print(f"  Total: {len(page_products)}")
            if len(page_products) == 0:
                empty_streak += 1
                if empty_streak >= 5 and not all_products:
                    print("Fail-fast: first 5 queries returned 0 products.")
                    break
            else:
                empty_streak = 0
    except QuotaExceeded as e:
        print(f"Aborting Shopee early: {e}")

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
