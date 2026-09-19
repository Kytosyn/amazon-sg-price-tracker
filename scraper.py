#!/usr/bin/env python3
"""DiskPrices Singapore - Amazon.sg scraper with fail-closed + optional proxy API."""

import os
import re
import sys
import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

from scrape_common import (
    DB_PATH,  # noqa: F401 — re-exported for callers/tests
    STORAGE_QUERIES,
    init_db,
    process_products,
    proxied_url,
    save_products,
    using_proxy,
)

init_db()

AMAZON_PAGES = 3  # search result pages per STORAGE_QUERIES term

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-SG,en;q=0.9',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
}


def _is_blocked(html: str) -> bool:
    low = html.lower()
    markers = [
        'enter the characters you see below',
        '/errors/validatecaptcha',
        'api-services-support@amazon.com',
        'sorry, we just need to make sure you\'re not a robot',
        'automated access',
    ]
    return any(m in low for m in markers)

def scrape_page(session, query, page=1, retries=3):
    items = []
    target = f"https://www.amazon.sg/s?k={quote_plus(query)}&page={page}"
    url = proxied_url(target)

    for attempt in range(retries):
        try:
            resp = session.get(url, headers=HEADERS, timeout=40)
            if resp.status_code == 200:
                if _is_blocked(resp.text):
                    print(f"  BLOCKED/captcha on '{query}' page {page}")
                    time.sleep((attempt + 1) * 8)
                    continue
                soup = BeautifulSoup(resp.text, 'html.parser')
                cards = soup.select('[data-component-type="s-search-result"]')
                if not cards:
                    cards = soup.find_all('div', {'data-asin': True})
                for p in cards:
                    try:
                        asin = p.get('data-asin')
                        if not asin:
                            continue
                        t = p.find('h2')
                        title = t.get_text(strip=True) if t else ""
                        if not title:
                            tn = p.select_one('span.a-text-normal')
                            title = tn.get_text(strip=True) if tn else ""
                        pr = p.select_one('span.a-price span.a-offscreen') or p.find('span', class_='a-price-whole')
                        pt = pr.get_text(strip=True) if pr else "0"
                        price = float(re.sub(r'[^\d.]', '', pt) or 0)
                        im = p.find('img', class_='s-image')
                        iu = im.get('src', '') if im else ""
                        if title and price > 0:
                            items.append({
                                'title': title,
                                'url': f'https://www.amazon.sg/dp/{asin}',
                                'image_url': iu,
                                'price': price,
                            })
                    except Exception:
                        continue
                return items
            if resp.status_code in (503, 429):
                time.sleep((attempt + 1) * 10)
                continue
            print(f"  HTTP {resp.status_code} on '{query}' page {page}")
            return items
        except Exception as e:
            print(f"  request error: {e}")
            time.sleep(5)
    return items

def main():
    session = requests.Session()
    print(f"Proxy API: {'yes' if using_proxy() else 'no (direct)'}")
    try:
        session.get(proxied_url("https://www.amazon.sg"), headers=HEADERS, timeout=30)
    except Exception as e:
        print(f"Warmup failed: {e}")
    time.sleep(2)

    queries = STORAGE_QUERIES

    all_products = []
    empty_streak = 0
    for q in queries:
        print(f"Scraping: {q}")
        page_products = []
        for page in range(1, AMAZON_PAGES + 1):
            items = scrape_page(session, q, page)
            products = process_products(items)
            page_products.extend(products)
            all_products.extend(products)
            time.sleep(random.uniform(0.8, 1.8))
        print(f"  Total: {len(page_products)}")
        if len(page_products) == 0:
            empty_streak += 1
            if empty_streak >= 5 and not all_products:
                print("Fail-fast: first 5 queries returned 0 products (likely blocked).")
                break
        else:
            empty_streak = 0

    # dedupe by url keeping first
    deduped = {}
    for p in all_products:
        deduped.setdefault(p['url'], p)
    all_products = list(deduped.values())
    all_products.sort(key=lambda p: (p['capacity_tb'] >= 1, -p['capacity_tb']), reverse=True)

    print(f"\n=== Grand total: {len(all_products)} ===")
    if len(all_products) == 0:
        print("ERROR: scrape returned 0 products — refusing to overwrite with empty results.")
        print("Hint: set SCRAPERAPI_KEY or ZENROWS_API_KEY repo secret for GitHub Actions.")
        sys.exit(1)

    save_products(all_products)

if __name__ == '__main__':
    main()
