#!/usr/bin/env python3
"""DiskPrices Singapore — Shopee.sg search via Apify (default) or ZenRows.

Primary SEA path after BuyWhere / official affiliate APIs stalled.

Provider selection (``SHOPEE_PROVIDER``, default ``auto``):
  - ``apify``   — Apify Actor ``lergassy/shopee-scraper`` (requires ``APIFY_TOKEN``)
  - ``zenrows`` — ZenRows HTML/XHR path (requires ``ZENROWS_API_KEY``)
  - ``auto``    — Apify if ``APIFY_TOKEN`` set, else ZenRows if ``ZENROWS_API_KEY``

Soft-fails by default (``SEA_SOFT_FAIL=1``) so a Shopee outage does not block
Amazon export.

Apify cost (spike eYXIMez1kh3nCa6gd, 2026-09-24): ~$0.01/item observed
($0.46 for 50 items). Hard-cap with ``APIFY_SHOPEE_MAX_ITEMS`` (default 100).
Price field from the Actor is **integer SGD cents** → divide by 100.

ZenRows fetch strategy (post-#9 RESP001) remains as optional fallback:
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

# Shorter list for SEA cost/latency (matches Lazada SEA_QUERIES).
# Apify uses the same list but hard-caps total items via APIFY_SHOPEE_MAX_ITEMS
# (not per-term) so one Actor run covers all terms under a spend ceiling.
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

# Apify Actor (store: lergassy/shopee-scraper). Spike run eYXIMez1kh3nCa6gd.
APIFY_ACTOR_ID = "lergassy~shopee-scraper"
APIFY_API_BASE = "https://api.apify.com/v2"
# Spike: ~$0.01/item. Default 100 ≈ $1/run ceiling; cron is every 30m so keep
# APIFY_SHOPEE_MAX_ITEMS low or leave ZENROWS_PAUSED/SCRAPE_PAUSED handling
# so Apify only runs when intended.
DEFAULT_APIFY_MAX_ITEMS = 100
APIFY_COST_PER_ITEM_USD = 0.01  # observed; logged as estimate only
APIFY_WAIT_FOR_FINISH_SEC = 300
APIFY_PRICE_CENTS_DIVISOR = 100  # Actor price is integer SGD cents

# ZenRows / unofficial search_items path uses Shopee micros.
ZENROWS_PRICE_DIVISOR = 100_000


class QuotaExceeded(RuntimeError):
    """ZenRows AUTH004 / HTTP 402."""


SEARCH_API = "https://shopee.sg/api/v4/search/search_items"
SEARCH_HTML = "https://shopee.sg/search"
PRICE_DIVISOR = ZENROWS_PRICE_DIVISOR  # retained name for ZenRows helpers

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


def resolve_shopee_provider() -> str:
    """Return ``apify`` or ``zenrows`` based on env (never prints secrets)."""
    raw = os.environ.get("SHOPEE_PROVIDER", "auto").strip().lower() or "auto"
    has_apify = bool(os.environ.get("APIFY_TOKEN", "").strip())
    has_zenrows = bool(os.environ.get("ZENROWS_API_KEY", "").strip())

    if raw in ("apify", "zenrows"):
        return raw
    if raw != "auto":
        print(f"Unknown SHOPEE_PROVIDER={raw!r}; treating as auto")
    if has_apify:
        return "apify"
    if has_zenrows:
        return "zenrows"
    return "none"


def apify_max_items() -> int:
    raw = os.environ.get("APIFY_SHOPEE_MAX_ITEMS", "").strip()
    if not raw:
        return DEFAULT_APIFY_MAX_ITEMS
    try:
        n = int(raw)
    except ValueError:
        print(f"Invalid APIFY_SHOPEE_MAX_ITEMS={raw!r}; using {DEFAULT_APIFY_MAX_ITEMS}")
        return DEFAULT_APIFY_MAX_ITEMS
    if n < 1:
        print(f"APIFY_SHOPEE_MAX_ITEMS={n} < 1; using {DEFAULT_APIFY_MAX_ITEMS}")
        return DEFAULT_APIFY_MAX_ITEMS
    # Hard ceiling to avoid accidental large spend (cron is */30).
    if n > 200:
        print(f"APIFY_SHOPEE_MAX_ITEMS={n} capped at 200 (spend guard)")
        return 200
    return n


def require_zenrows() -> None:
    if not os.environ.get("ZENROWS_API_KEY", "").strip():
        sea_soft_exit(
            "ZENROWS_API_KEY is not set — refusing unofficial Shopee scrape without proxy. "
            "Add the same GitHub secret used by Amazon, or set APIFY_TOKEN for the Apify path."
        )


def require_apify() -> str:
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token:
        sea_soft_exit(
            "APIFY_TOKEN is not set — refusing Apify Shopee scrape. "
            "Add GitHub secret APIFY_TOKEN, or set SHOPEE_PROVIDER=zenrows with ZENROWS_API_KEY."
        )
    return token


def _slugify(title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE)
    slug = re.sub(r"[\s_]+", "-", slug.strip()).strip("-")
    return slug[:80] or "item"


def _price_sgd(*candidates: Any) -> float:
    """ZenRows / search_items micros → SGD (÷100000 when large)."""
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


def _apify_price_sgd(*candidates: Any) -> float:
    """Apify Actor price is integer SGD cents → divide by 100."""
    for raw in candidates:
        if raw is None or raw == "":
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        if val <= 0:
            continue
        # Cents (29029 → 290.29). If already a small decimal, keep as-is.
        if val >= 100:  # clearly cents (or larger)
            val = val / APIFY_PRICE_CENTS_DIVISOR
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


def normalize_apify_item(item: dict) -> dict | None:
    """Map Apify ``lergassy/shopee-scraper`` row → process_products shape.

    Spike fields: title, price (cents), originalPrice, currency, url, shopId,
    itemId, imageUrl, searchTerm. Price ÷ 100 → SGD.
    """
    if not isinstance(item, dict):
        return None
    if item.get("type") and item.get("type") != "product":
        return None
    title = (item.get("title") or "").strip()
    url = (item.get("url") or "").strip()
    shop_id = item.get("shopId") or item.get("shopid")
    item_id = item.get("itemId") or item.get("itemid")
    if not url and shop_id is not None and item_id is not None:
        url = _product_url(shop_id, item_id, title or "item")
    price = _apify_price_sgd(item.get("price"))
    original = _apify_price_sgd(item.get("originalPrice"), item.get("original_price"))
    if original <= 0:
        original = price
    image = (item.get("imageUrl") or item.get("image_url") or "").strip()
    if image and not image.startswith("http"):
        image = _image_url(image)
    if not title or not url or price <= 0:
        return None
    seller = PLATFORM
    if shop_id is not None and str(shop_id).strip():
        seller = f"{PLATFORM}:{shop_id}"
    return {
        "title": title,
        "url": url,
        "image_url": image,
        "price": price,
        "original_price": original,
        "platform": PLATFORM,
        "seller": seller,
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
    """Fetch Shopee results for one keyword via ZenRows.

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


def fetch_apify_items(
    session: requests.Session,
    token: str,
    search_terms: list[str],
    max_items: int,
) -> list[dict]:
    """Run Apify Actor once and return normalized product dicts (soft-fail caller)."""
    actor_input = {
        "mode": "search",
        "country": "SG",
        "searchTerms": search_terms,
        "maxItems": max_items,
        "enrichProducts": False,
    }
    est_usd = max_items * APIFY_COST_PER_ITEM_USD
    print(
        f"Shopee Apify: actor={APIFY_ACTOR_ID} terms={len(search_terms)} "
        f"maxItems={max_items} enrichProducts=false "
        f"est_cost_usd≈${est_usd:.2f} (@~${APIFY_COST_PER_ITEM_USD}/item observed)"
    )
    # Token only in query string / Authorization — never print it.
    run_url = f"{APIFY_API_BASE}/acts/{APIFY_ACTOR_ID}/runs"
    try:
        resp = session.post(
            run_url,
            params={"token": token, "waitForFinish": APIFY_WAIT_FOR_FINISH_SEC},
            json=actor_input,
            timeout=APIFY_WAIT_FOR_FINISH_SEC + 60,
        )
    except requests.RequestException as e:
        print(f"Apify run request failed: {e}")
        return []

    if resp.status_code not in (200, 201):
        print(f"Apify run HTTP {resp.status_code}: {resp.text[:300]}")
        return []

    try:
        payload = resp.json()
    except ValueError:
        print(f"Apify run non-JSON: {resp.text[:200]}")
        return []

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        print(f"Apify run unexpected payload keys: {list(payload)[:10] if isinstance(payload, dict) else type(payload)}")
        return []

    run_id = data.get("id") or "?"
    status = data.get("status") or "?"
    usage_usd = data.get("usageTotalUsd")
    dataset_id = data.get("defaultDatasetId")
    print(
        f"Apify run id={run_id} status={status} "
        f"usageTotalUsd={usage_usd if usage_usd is not None else 'n/a'} "
        f"dataset={dataset_id or 'n/a'}"
    )
    if status not in ("SUCCEEDED", "SUCCEEDED_WITH_WARNINGS"):
        print(f"Apify run did not succeed (status={status}); statusMessage={data.get('statusMessage')!r}")
        return []
    if not dataset_id:
        print("Apify run missing defaultDatasetId")
        return []

    items_url = f"{APIFY_API_BASE}/datasets/{dataset_id}/items"
    try:
        items_resp = session.get(
            items_url,
            params={"token": token, "format": "json", "clean": "true"},
            timeout=120,
        )
    except requests.RequestException as e:
        print(f"Apify dataset fetch failed: {e}")
        return []
    if items_resp.status_code != 200:
        print(f"Apify dataset HTTP {items_resp.status_code}: {items_resp.text[:300]}")
        return []
    try:
        raw_items = items_resp.json()
    except ValueError:
        print(f"Apify dataset non-JSON: {items_resp.text[:200]}")
        return []
    if not isinstance(raw_items, list):
        print(f"Apify dataset expected list, got {type(raw_items).__name__}")
        return []

    print(f"Apify dataset raw items: {len(raw_items)}")
    out: list[dict] = []
    skipped = 0
    for row in raw_items:
        norm = normalize_apify_item(row) if isinstance(row, dict) else None
        if norm:
            out.append(norm)
        else:
            skipped += 1
    print(f"Apify normalized: {len(out)} products ({skipped} skipped/malformed)")
    if usage_usd is not None and len(raw_items) > 0:
        per = float(usage_usd) / len(raw_items)
        print(f"Apify cost: ${float(usage_usd):.4f} total, ~${per:.4f}/raw-item")
    elif len(raw_items) > 0:
        print(
            f"Apify cost: usageTotalUsd unavailable; "
            f"est≈${len(raw_items) * APIFY_COST_PER_ITEM_USD:.2f} "
            f"(@~${APIFY_COST_PER_ITEM_USD}/item)"
        )
    return out


def run_zenrows(session: requests.Session) -> list[dict]:
    require_zenrows()
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
    return all_products


def run_apify(session: requests.Session) -> list[dict]:
    token = require_apify()
    queries = SEA_QUERIES or STORAGE_QUERIES
    max_items = apify_max_items()
    try:
        items = fetch_apify_items(session, token, queries, max_items)
    except Exception as e:
        # Soft-fail path: never raise into hard-fail for SEA.
        print(f"Apify Shopee error: {type(e).__name__}: {e}")
        return []
    return process_products(items, default_platform=PLATFORM, default_seller=PLATFORM)


def main() -> None:
    init_db()
    provider = resolve_shopee_provider()
    print(f"Shopee provider: {provider} (SHOPEE_PROVIDER={os.environ.get('SHOPEE_PROVIDER', 'auto')!r})")

    if provider == "none":
        sea_soft_exit(
            "No Shopee provider available — set APIFY_TOKEN (preferred) or ZENROWS_API_KEY."
        )

    session = requests.Session()
    if provider == "apify":
        all_products = run_apify(session)
        label = "Apify"
    else:
        all_products = run_zenrows(session)
        label = "ZenRows"

    deduped: dict[str, dict] = {}
    for p in all_products:
        deduped.setdefault(p["url"], p)
    all_products = list(deduped.values())
    all_products.sort(key=lambda p: (p["capacity_tb"] >= 1, -p["capacity_tb"]), reverse=True)

    print(f"\n=== Shopee {label} grand total: {len(all_products)} ===")
    if len(all_products) == 0:
        sea_soft_exit(f"Shopee {label} scrape returned 0 storage products — fail-closed (soft).")

    save_products(all_products)
    print(f"Saved {len(all_products)} Shopee products.")


if __name__ == "__main__":
    main()
