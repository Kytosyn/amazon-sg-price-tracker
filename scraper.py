#!/usr/bin/env python3
"""DiskPrices Singapore - Broad scraper for all storage devices."""

import re
import time
import random
import sqlite3
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

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
        if kw in tl: return True
    for kw in ['hdd', 'hard drive', 'hard disk', 'mechanical']:
        if kw in tl: return False
    return False

def is_real_storage(title):
    """Whitelist: only include actual storage devices."""
    t = title.lower()
    
    # Must have capacity
    if not re.search(r'\d+\s*tb|\d+\s*gb', t):
        return False
    
    # Exclude accessories
    accessory_kw = [
        'case', 'enclosure', 'stand', 'cable', 'adapter', 'mount', 'bracket',
        'dock', 'pouch', 'bag', 'box', 'sleeve', 'protector', 'sticker', 'label',
        'decal', 'skin', 'wrap', 'cover', 'tray', 'caddy', 'bay', 'rail',
        'installation kit', 'mounting kit', 'bracket kit', 'tool kit',
        'carrying case', 'storage case', 'travel case',
        'hdd stand', 'hdd enclosure', 'hdd case', 'hdd carrying case',
        'hard drive stand', 'hard drive enclosure', 'hard drive case',
        'hard disk stand', 'hard disk enclosure', 'hard disk stand',
        'usb to sata', 'sata cable', 'power cable', 'data cable',
        'docking station', 'cloner', 'duplicator',
        'sabrent', 'maiwo', 'ssk', 'avolusion', 'intenso memory case', 'modustech facet',
    ]
    for kw in accessory_kw:
        if kw in t:
            return False
    
    # Must be storage
    storage_kw = ['hdd', 'hard drive', 'hard disk', 'ssd', 'solid state', 'nvme', 
                  'sata', 'storage', 'internal', 'external', 'portable', 'desktop',
                  'enterprise', 'nas', 'data center', 'server', 'drive']
    return any(kw in t for kw in storage_kw)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
}

def scrape_page(session, query, page=1, retries=3):
    items = []
    url = f"https://www.amazon.sg/s?k={quote_plus(query)}&page={page}"
    
    for attempt in range(retries):
        try:
            resp = session.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for p in soup.find_all('div', {'data-asin': True}):
                    try:
                        asin = p.get('data-asin')
                        if not asin: continue
                        t = p.find('h2')
                        title = t.get_text(strip=True) if t else ""
                        pr = p.find('span', class_='a-price-whole')
                        pt = pr.get_text(strip=True) if pr else "0"
                        price = float(re.sub(r'[^\d.]', '', pt))
                        im = p.find('img', class_='s-image')
                        iu = im.get('src', '') if im else ""
                        if title and price > 0:
                            items.append({'title': title, 'url': f'https://www.amazon.sg/dp/{asin}',
                                          'image_url': iu, 'price': price})
                    except:
                        continue
                return items
            elif resp.status_code == 503:
                time.sleep((attempt + 1) * 10)
            else:
                return items
        except:
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
            c.execute('''UPDATE products SET price=?, original_price=?, cost_per_tb=?, last_seen=?, is_active=1 WHERE url=?''',
                (p['price'], p['original_price'], p['cost_per_tb'], now, p['url']))
    conn.commit()
    conn.close()

def main():
    session = requests.Session()
    session.get("https://www.amazon.sg", headers=HEADERS, timeout=15)
    time.sleep(2)
    
    queries = [
        # Internal HDDs
        'internal hard drive', 'internal hdd', 'internal hard disk',
        'wd gold', 'wd red', 'wd purple', 'wd blue', 'wd black',
        'seagate barracuda', 'seagate ironwolf', 'seagate exos',
        'toshiba n300', 'toshiba x300', 'toshiba mg',
        # External HDDs
        'external hard drive', 'external hdd', 'portable hard drive',
        'wd elements', 'wd my book', 'wd my passport',
        'seagate expansion', 'seagate backup plus',
        'toshiba canvio', 'lacie', 'buffalo',
        # Internal SSDs
        'internal ssd', 'nvme ssd', 'm.2 ssd', 'sata ssd',
        'samsung 870', 'samsung 980', 'samsung 990',
        'crucial mx500', 'crucial p5', 'crucial t500',
        'wd blue ssd', 'wd black ssd', 'kingston nv2',
        # External SSDs
        'external ssd', 'portable ssd',
        'samsung t7', 'samsung t9', 'sandisk extreme',
        'crucial x10', 'crucial x9', 'kingston xs2000',
        # NAS drives
        'nas hard drive', 'nas storage',
        'synology', 'qnap',
        # Enterprise
        'enterprise hard drive', 'enterprise ssd',
        'server hard drive', 'data center drive',
        # General
        'hard drive', 'hdd', 'ssd', 'solid state drive',
        'storage drive', 'computer drive', 'laptop drive',
        'desktop drive', 'pc drive', 'mac drive',
    ]
    
    all_products = []
    for q in queries:
        print(f"Scraping: {q}")
        for page in [1, 2]:
            items = scrape_page(session, q, page)
            products = process_products(items)
            all_products.extend(products)
            time.sleep(random.uniform(0.5, 1.5))
        print(f"  Total: {len(products)}")
    
    # Sort: TB first (descending), then GB (descending)
    all_products.sort(key=lambda p: (p['capacity_tb'] >= 1, -p['capacity_tb']), reverse=True)
    
    save_products(all_products)
    print(f"\n=== Grand total: {len(all_products)} ===")

if __name__ == '__main__':
    main()
