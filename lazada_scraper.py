#!/usr/bin/env python3
"""DiskPrices Singapore — Lazada.sg catalog search via ZenRows (ajax JSON).

Primary SEA path after BuyWhere / official affiliate APIs stalled.
Requires ZENROWS_API_KEY (same secret as Amazon). Soft-fails by default
(SEA_SOFT_FAIL=1) so a Lazada outage does not block Amazon export.
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

PLATFORM = "Lazada"
SEARCH_BASE = "https://www.lazada.sg/catalog/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-SG,en;q=0.9",
    "Referer": "https://www.lazada.sg/",
    "X-Requested-With": "XMLHttpRequest",
}


def require_zenrows() -> None:
    if not os.environ.get("ZENROWS_API_KEY", "").strip():
        sea_soft_exit(
            "ZENROWS_API_KEY is not set — refusing unofficial Lazada scrape without proxy. "
            "Add the same GitHub secret used by Amazon."
        )


def _parse_price(*candidates: Any) -> float:
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
        if 0 < val < 50_000:
            return val
    return 0.0


def _abs_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return "https://www.lazada.sg" + u
    if not u.startswith("http"):
        return "https://www.lazada.sg/" + u.lstrip("/")
    return u


def _normalize_item(item: dict) -> dict | None:
    title = (item.get("name") or item.get("title") or "").strip()
    url = _abs_url(
        item.get("productUrl")
        or item.get("itemUrl")
        or item.get("url")
        or ""
    )
    price = _parse_price(
        item.get("price"),
        item.get("priceShow"),
        item.get("originalPrice"),
        item.get("originalPriceShow"),
    )
    if not title or not url or price <= 0:
        return None
    original = _parse_price(
        item.get("originalPrice"),
        item.get("originalPriceShow"),
        price,
    ) or price
    image = item.get("image") or item.get("thumbnail") or item.get("img") or ""
    if isinstance(image, list):
        image = image[0] if image else ""
    seller = (item.get("sellerName") or item.get("brandName") or PLATFORM).strip() or PLATFORM
    return {
        "title": title,
        "url": url,
        "image_url": _abs_url(str(image)) if image else "",
        "price": price,
        "original_price": original,
        "platform": PLATFORM,
        "seller": seller,
    }


def _extract_list_items(data: Any) -> list:
    if not isinstance(data, dict):
        return []
    mods = data.get("mods")
    if isinstance(mods, dict) and isinstance(mods.get("listItems"), list):
        return mods["listItems"]
    # Some payloads nest under mainInfo / data
    for key in ("listItems", "products", "items"):
        if isinstance(data.get(key), list):
            return data[key]
    nested = data.get("data")
    if isinstance(nested, dict):
        return _extract_list_items(nested)
    return []


def search_catalog(session: requests.Session, keyword: str, page: int = 1) -> list[dict]:
    params = {
        "q": keyword,
        "ajax": "true",
        "page": page,
        "_keyori": "ss",
        "from": "input",
        "isFirstRequest": "true" if page == 1 else "false",
    }
    url = f"{SEARCH_BASE}?{urlencode(params, quote_via=quote_plus)}"
    # Lazada ajax sometimes needs light JS; try premium_proxy first, then js_render.
    resp = zenrows_get(session, url, headers=HEADERS, timeout=70)
    if resp is None or resp.status_code != 200 or not _looks_like_json(resp):
        resp = zenrows_get(
            session,
            url,
            headers=HEADERS,
            timeout=90,
            extra_params={"js_render": "true", "wait": "3000"},
        )
    if resp is None:
        print(f"  no response for '{keyword}' page {page}")
        return []
    if resp.status_code != 200:
        print(f"  HTTP {resp.status_code} for '{keyword}' page {page}: {resp.text[:200]}")
        return []
    data = _parse_payload(resp)
    if data is None:
        snippet = resp.text[:120].replace("\n", " ")
        print(f"  Non-JSON/unparseable for '{keyword}': {snippet}")
        return []
    raw_items = _extract_list_items(data)
    out: list[dict] = []
    for entry in raw_items:
        if not isinstance(entry, dict):
            continue
        norm = _normalize_item(entry)
        if norm:
            out.append(norm)
    if not out and raw_items:
        print(f"  {len(raw_items)} raw items but none normalized for '{keyword}'")
    return out


def _looks_like_json(resp: requests.Response) -> bool:
    ctype = (resp.headers.get("Content-Type") or "").lower()
    text = (resp.text or "").lstrip()
    return "json" in ctype or text.startswith("{") or text.startswith("[")


def _parse_payload(resp: requests.Response) -> dict | None:
    text = resp.text or ""
    try:
        data = resp.json()
        if isinstance(data, dict):
            return data
    except ValueError:
        pass
    # HTML fallback: window.runParams / window.pageData
    for pattern in (
        r"window\.runParams\s*=\s*(\{.*?\});?\s*(?:window\.|</script>)",
        r"window\.pageData\s*=\s*(\{.*?\});?\s*(?:window\.|</script>)",
    ):
        m = re.search(pattern, text, flags=re.DOTALL)
        if not m:
            continue
        try:
            import json

            data = json.loads(m.group(1))
            if isinstance(data, dict):
                return data
        except ValueError:
            continue
    return None


def main() -> None:
    require_zenrows()
    init_db()
    session = requests.Session()
    print(f"Proxy API: {'yes' if using_proxy() else 'no'}")

    all_products: list[dict] = []
    empty_streak = 0
    for q in STORAGE_QUERIES:
        print(f"Lazada ZenRows: {q}")
        page_products: list[dict] = []
        for page in (1, 2):
            items = search_catalog(session, q, page=page)
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

    deduped: dict[str, dict] = {}
    for p in all_products:
        deduped.setdefault(p["url"], p)
    all_products = list(deduped.values())
    all_products.sort(key=lambda p: (p["capacity_tb"] >= 1, -p["capacity_tb"]), reverse=True)

    print(f"\n=== Lazada ZenRows grand total: {len(all_products)} ===")
    if len(all_products) == 0:
        sea_soft_exit("Lazada ZenRows scrape returned 0 storage products — fail-closed (soft).")

    save_products(all_products)
    print(f"Saved {len(all_products)} Lazada products.")


if __name__ == "__main__":
    main()
