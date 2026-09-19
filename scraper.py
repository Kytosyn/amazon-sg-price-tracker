#!/usr/bin/env python3
"""DiskPrices Singapore - Amazon.sg scraper with fail-closed + optional proxy API."""

import os
import re
import sys
import time
import random
import sqlite3
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, quote

DB_PATH = "./diskprices.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL,
        title TEXT NOT NULL,
        url TEXT UNIQUE NOT NULL,
        image_url TEXT,
        price REAL NOT NULL,
        original_price REAL,
        capacity_gb REAL NOT NULL,
        capacity_tb REAL NOT NULL,
        is_ssd BOOLEAN NOT NULL,
        cost_per_tb REAL NOT NULL,
        rating REAL DEFAULT 0,
        review_count INTEGER DEFAULT 0,
        seller TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT 1
    )''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_url ON products(url)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_capacity ON products(capacity_tb)')
    conn.commit()
    conn.close()

init_db()

def parse_capacity(title):
    tl = title.lower()
    m = re.search(r'(\d+(?:\.\d+)?)\s*tb(?!w)', tl)
    if m:
        tb = float(m.group(1))
        return tb * 1000, tb
    m = re.search(r'(\d+(?:\.\d+)?)\s*gb(?!w)', tl)
    if m:
        gb = float(m.group(1))
        return gb, gb / 1000
    return 0, 0

def is_ssd(title):
    tl = title.lower()
    for kw in ['ssd', 'solid state', 'nvme', 'm.2', 'pcie']:
        if kw in tl:
            return True
    for kw in ['hdd', 'hard drive', 'hard disk', 'mechanical']:
        if kw in tl:
            return False
    return False

def is_real_storage(title):
    t = title.lower()
    if not re.search(r'\d+\s*tb|\d+\s*gb', t):
        return False
    accessory_kw = [
        'case', 'enclosure', 'stand', 'cable', 'adapter', 'mount', 'bracket',
        'dock', 'pouch', 'bag', 'box', 'sleeve', 'protector', 'sticker', 'label',
        'decal', 'skin', 'wrap', 'cover', 'tray', 'caddy', 'bay', 'rail',
        'installation kit', 'mounting kit', 'bracket kit', 'tool kit',
        'carrying case', 'storage case', 'travel case',
        'hdd stand', 'hdd enclosure', 'hdd case', 'hdd carrying case',
    ]
    if any(kw in t for kw in accessory_kw):
        return False
    storage_kw = [
        'hdd', 'hard drive', 'hard disk', 'ssd', 'solid state', 'nvme',
        'sata', 'storage', 'internal', 'external', 'portable', 'desktop',
        'enterprise', 'nas', 'data center', 'server', 'drive',
    ]
    return any(kw in t for kw in storage_kw)

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

def _proxied_url(url: str) -> str:
    """Optional ScraperAPI / ZenRows / custom proxy prefix via env."""
    scraperapi = os.environ.get('SCRAPERAPI_KEY', '').strip()
    if scraperapi:
        return f"http://api.scraperapi.com?api_key={quote(scraperapi)}&url={quote(url, safe='')}&country_code=sg"
    zenrows = os.environ.get('ZENROWS_API_KEY', '').strip()
    if zenrows:
        return f"https://api.zenrows.com/v1/?apikey={quote(zenrows)}&url={quote(url, safe='')}&premium_proxy=true"
    return url

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
    url = _proxied_url(target)

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

def process_products(items):
    products = []
    seen = set()
    for item in items:
        title = item.get('title', '')
        price = item.get('price', 0)
        url = item.get('url', '')
        if price <= 0 or url in seen:
            continue
        if not is_real_storage(title):
            continue
        cap_gb, cap_tb = parse_capacity(title)
        if cap_tb <= 0:
            continue
        seen.add(url)
        products.append({
            'platform': 'Amazon.sg',
            'title': title,
            'url': url,
            'image_url': item.get('image_url', ''),
            'price': price,
            'original_price': price,
            'capacity_gb': cap_gb,
            'capacity_tb': cap_tb,
            'is_ssd': is_ssd(title),
            'cost_per_tb': price / cap_tb if cap_tb > 0 else 0,
            'seller': 'Amazon.sg',
        })
    return products

def save_products(products):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    for p in products:
        try:
            c.execute('''INSERT INTO products
                (platform,title,url,image_url,price,original_price,capacity_gb,capacity_tb,is_ssd,cost_per_tb,seller,timestamp,first_seen,last_seen,is_active)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)''',
                (p['platform'], p['title'], p['url'], p['image_url'], p['price'], p['original_price'],
                 p['capacity_gb'], p['capacity_tb'], p['is_ssd'], p['cost_per_tb'], p['seller'],
                 now, now, now))
        except sqlite3.IntegrityError:
            c.execute('''UPDATE products SET price=?, original_price=?, cost_per_tb=?, timestamp=?, last_seen=?, is_active=1 WHERE url=?''',
                (p['price'], p['original_price'], p['cost_per_tb'], now, now, p['url']))
    conn.commit()
    conn.close()

def main():
    session = requests.Session()
    using_proxy = bool(os.environ.get('SCRAPERAPI_KEY') or os.environ.get('ZENROWS_API_KEY'))
    print(f"Proxy API: {'yes' if using_proxy else 'no (direct)'}")
    try:
        session.get(_proxied_url("https://www.amazon.sg"), headers=HEADERS, timeout=30)
    except Exception as e:
        print(f"Warmup failed: {e}")
    time.sleep(2)

    queries = [
        'internal hard drive', 'internal hdd', 'wd gold', 'wd red', 'wd purple',
        'wd blue', 'wd black', 'seagate barracuda', 'seagate ironwolf', 'seagate exos',
        'toshiba n300', 'toshiba x300',
        'external hard drive', 'external hdd', 'portable hard drive',
        'wd elements', 'wd my book', 'wd my passport',
        'seagate expansion', 'toshiba canvio',
        'internal ssd', 'nvme ssd', 'm.2 ssd', 'sata ssd',
        'samsung 870', 'samsung 980', 'samsung 990',
        'crucial mx500', 'wd blue ssd', 'kingston nv2',
        'external ssd', 'portable ssd', 'samsung t7', 'samsung t9', 'sandisk extreme',
        'nas hard drive', 'enterprise hard drive', 'hard drive', 'ssd',
    ]

    all_products = []
    empty_streak = 0
    for q in queries:
        print(f"Scraping: {q}")
        page_products = []
        for page in [1, 2]:
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
