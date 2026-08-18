#!/usr/bin/env python3
"""
DiskPrices Singapore - Multi-Platform HDD/SSD Price Comparison
Uses requests + BeautifulSoup with retry logic and proper headers.
"""

import re
import time
import random
import sqlite3
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

DB_PATH = "./diskprices.db"

# ─── Database ──────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
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
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            price REAL NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (url) REFERENCES products(url)
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_products_platform ON products(platform)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_products_ssd ON products(is_ssd)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_products_cost ON products(cost_per_tb)')
    conn.commit()
    conn.close()

init_db()

# ─── Capacity Parser ───────────────────────────────────────────

def parse_capacity(title: str) -> tuple:
    title_lower = title.lower()
    tb_match = re.search(r'(\d+(?:\.\d+)?)\s*tb(?!w)', title_lower)
    if tb_match:
        tb = float(tb_match.group(1))
        return tb * 1000, tb
    gb_match = re.search(r'(\d+(?:\.\d+)?)\s*gb(?!w)', title_lower)
    if gb_match:
        gb = float(gb_match.group(1))
        return gb, gb / 1000
    return 0, 0

def is_ssd(title: str) -> bool:
    title_lower = title.lower()
    ssd_keywords = ['ssd', 'solid state', 'nvme', 'm.2', 'pcie']
    hdd_keywords = ['hdd', 'hard drive', 'hard disk', 'mechanical']
    for kw in ssd_keywords:
        if kw in title_lower:
            return True
    for kw in hdd_keywords:
        if kw in title_lower:
            return False
    return False

def is_not_accessory(title: str) -> bool:
    """Filter out cases, enclosures, adapters, cables, and other non-drive items."""
    title_lower = title.lower()
    exclude_keywords = [
        'case', 'enclosure', 'adapter', 'cable', 'hub', 'reader',
        'mount', 'bracket', 'dock', 'station', ' converter',
        'pouch', 'bag', 'box', 'sleeve', 'protector',
        'stylus', 'pen', 'remote', 'keyboard', 'mouse',
        'cleaner', 'cleaning', 'thermal', 'paste', 'compound',
        'screw', 'screwdriver', 'tool', 'kit',
        'ram', 'memory', 'motherboard', 'cpu', 'gpu', 'graphics card',
        'power supply', 'psu', 'fan', 'heatsink', 'cooler',
        'monitor', 'display', 'screen', 'webcam', 'headset',
        'router', 'switch', 'modem', 'access point',
        'printer', 'scanner', 'projector',
        'tv', 'television', 'soundbar', 'speaker',
        'game', 'controller', 'console',
        'license', 'software', 'warranty',
    ]
    for kw in exclude_keywords:
        if kw in title_lower:
            return True
    return False

# ─── Amazon Scraper ────────────────────────────────────────────

def scrape_amazon_page(query: str, page: int = 1, retries: int = 3) -> list:
    items = []
    url = f"https://www.amazon.sg/s?k={quote_plus(query)}&page={page}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }
    
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            
            if resp.status_code == 503:
                wait_time = (attempt + 1) * 5
                print(f"  503 error, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            products = soup.find_all('div', {'data-asin': True})
            
            for product in products:
                try:
                    asin = product.get('data-asin')
                    if not asin:
                        continue
                    
                    title_el = product.find('h2')
                    title = title_el.get_text(strip=True) if title_el else ""
                    
                    price_el = product.find('span', class_='a-price-whole')
                    price_text = price_el.get_text(strip=True) if price_el else "0"
                    price = float(re.sub(r'[^\d.]', '', price_text))
                    
                    img = product.find('img', class_='s-image')
                    img_url = img.get('src', '') if img else ""
                    
                    if title and price > 0:
                        items.append({
                            'title': title,
                            'url': f"https://www.amazon.sg/dp/{asin}",
                            'image_url': img_url,
                            'price': price,
                            'original_price': price,
                            'rating': 0,
                            'review_count': 0,
                            'seller': 'Amazon.sg',
                        })
                except:
                    continue
            
            return items
            
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                wait_time = (attempt + 1) * 3
                print(f"  Request error, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
            else:
                print(f"  Failed after {retries} attempts: {e}")
    
    return items

def scrape_amazon(query: str, max_pages: int = 2) -> list:
    all_items = []
    for page in range(1, max_pages + 1):
        items = scrape_amazon_page(query, page)
        all_items.extend(items)
        print(f"  Page {page}: {len(items)} items")
        time.sleep(random.uniform(1, 2))
    return all_items

# ─── Capacity Filter ───────────────────────────────────────────

MIN_CAPACITY_TB = 10  # Only track drives 10TB+

def meets_capacity_requirement(capacity_tb: float) -> bool:
    """Only track high-capacity drives (10TB+)."""
    return capacity_tb >= MIN_CAPACITY_TB

# ─── Price Processor ───────────────────────────────────────────

def process_storage_products(items: list, platform: str) -> list:
    products = []
    seen = set()
    for item in items:
        title = item.get('title', '')
        price = item.get('price', 0)
        url = item.get('url', '')
        if price <= 0 or url in seen:
            continue
        # Filter out non-storage accessories
        if is_not_accessory(title):
            continue
        capacity_gb, capacity_tb = parse_capacity(title)
        # Only 10TB+ drives
        if not meets_capacity_requirement(capacity_tb):
            continue
        seen.add(url)
        cost_per_tb = price / capacity_tb
        products.append({
            'platform': platform,
            'title': title,
            'url': url,
            'image_url': item.get('image_url', ''),
            'price': price,
            'original_price': item.get('original_price', price),
            'capacity_gb': capacity_gb,
            'capacity_tb': capacity_tb,
            'is_ssd': is_ssd(title),
            'cost_per_tb': cost_per_tb,
            'rating': 0,
            'review_count': 0,
            'seller': item.get('seller', ''),
            'timestamp': datetime.now().isoformat(),
        })
    return products

# ─── Database ──────────────────────────────────────────────────

def save_products(products: list):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for p in products:
        try:
            c.execute('''INSERT OR REPLACE INTO products 
                (platform, title, url, image_url, price, original_price, capacity_gb, capacity_tb, is_ssd, cost_per_tb, rating, review_count, seller, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (p['platform'], p['title'], p['url'], p['image_url'], p['price'], p['original_price'],
                 p['capacity_gb'], p['capacity_tb'], p['is_ssd'], p['cost_per_tb'], p['rating'],
                 p['review_count'], p['seller'], p['timestamp']))
            c.execute('INSERT INTO price_history (url, price) VALUES (?, ?)', (p['url'], p['price']))
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()

# ─── Main ──────────────────────────────────────────────────────

def scrape_all():
    queries = [
        # High-capacity internal hard drives (10TB+)
        'hard drive 10tb', 'hard drive 12tb', 'hard drive 14tb', 'hard drive 16tb', 'hard drive 18tb', 'hard drive 20tb', 'hard drive 22tb',
        'hard disk 10tb', 'hard disk 12tb', 'hard disk 14tb', 'hard disk 16tb', 'hard disk 18tb',
        'internal hard drive 10tb', 'internal hard drive 12tb', 'internal hard drive 14tb', 'internal hard drive 16tb', 'internal hard drive 18tb', 'internal hard drive 20tb',
        # Enterprise / NAS drives
        'seagate ironwolf 10tb', 'seagate ironwolf 12tb', 'seagate ironwolf 16tb', 'seagate ironwolf 18tb', 'seagate ironwolf pro 20tb',
        'wd red plus 10tb', 'wd red plus 12tb', 'wd red plus 14tb', 'wd red pro 16tb', 'wd red pro 18tb', 'wd red pro 20tb',
        'seagate exos 16tb', 'seagate exos 18tb', 'seagate exos 20tb', 'seagate exos 22tb',
        'toshiba mg09 16tb', 'toshiba mg09 18tb', 'toshiba mg10 20tb', 'toshiba mg10 22tb',
        'wd gold 16tb', 'wd gold 18tb', 'wd gold 20tb', 'wd gold 22tb',
        'wd ultrastar 16tb', 'wd ultrastar 18tb', 'wd ultrastar 20tb', 'wd ultrastar 22tb',
        # NAS drives
        'nas hard drive 10tb', 'nas hard drive 12tb', 'nas hard drive 14tb', 'nas hard drive 16tb', 'nas hard drive 18tb',
        'synology 10tb', 'synology 12tb', 'synology 16tb',
        'qnap 10tb', 'qnap 12tb', 'qnap 16tb',
        # Data center drives
        'data center hard drive 10tb', 'data center hard drive 12tb', 'data center hard drive 14tb', 'data center hard drive 16tb', 'data center hard drive 18tb', 'data center hard drive 20tb',
        'enterprise hard drive 10tb', 'enterprise hard drive 12tb', 'enterprise hard drive 14tb', 'enterprise hard drive 16tb', 'enterprise hard drive 18tb', 'enterprise hard drive 20tb',
        'server hard drive 10tb', 'server hard drive 12tb', 'server hard drive 14tb', 'server hard drive 16tb', 'server hard drive 18tb',
        # External high-capacity drives
        'external hard drive 10tb', 'external hard drive 12tb', 'external hard drive 14tb', 'external hard drive 16tb', 'external hard drive 18tb', 'external hard drive 20tb',
        'desktop hard drive 10tb', 'desktop hard drive 12tb', 'desktop hard drive 14tb', 'desktop hard drive 16tb', 'desktop hard drive 18tb', 'desktop hard drive 20tb',
        # Specific high-capacity models
        'wd elements 10tb', 'wd elements 12tb', 'wd elements 14tb', 'wd elements 16tb', 'wd elements 18tb', 'wd elements 20tb', 'wd elements 22tb',
        'wd my book 10tb', 'wd my book 12tb', 'wd my book 14tb', 'wd my book 16tb', 'wd my book 18tb', 'wd my book 20tb', 'wd my book 22tb',
        'seagate expansion 10tb', 'seagate expansion 12tb', 'seagate expansion 14tb', 'seagate expansion 16tb', 'seagate expansion 18tb', 'seagate expansion 20tb',
        'seagate backup plus 10tb', 'seagate backup plus 12tb', 'seagate backup plus 14tb', 'seagate backup plus 16tb', 'seagate backup plus 18tb',
        'lacie 10tb', 'lacie 12tb', 'lacie 14tb', 'lacie 16tb', 'lacie 18tb', 'lacie 20tb',
        # High-capacity SSDs (rare but exist)
        'ssd 10tb', 'ssd 15tb', 'ssd 16tb', 'ssd 30tb',
        'enterprise ssd 10tb', 'enterprise ssd 15tb', 'enterprise ssd 16tb', 'enterprise ssd 30tb',
    ]
    
    all_products = []
    for query in queries:
        print(f"Scraping: {query}")
        items = scrape_amazon(query, max_pages=3)
        products = process_storage_products(items, 'Amazon.sg')
        all_products.extend(products)
        print(f"  Total: {len(products)}\n")
        time.sleep(random.uniform(2, 4))
    
    save_products(all_products)
    print(f"=== Grand total: {len(all_products)} ===")
    return all_products

if __name__ == '__main__':
    scrape_all()
