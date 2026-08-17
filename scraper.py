#!/usr/bin/env python3
"""
DiskPrices Singapore - Multi-Platform HDD/SSD Price Comparison
Uses requests + BeautifulSoup with pagination for maximum coverage.
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
SESSION = requests.Session()

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

# ─── Amazon Scraper ────────────────────────────────────────────

def scrape_amazon_page(query: str, page: int = 1) -> list:
    items = []
    url = f"https://www.amazon.sg/s?k={quote_plus(query)}&page={page}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    try:
        resp = SESSION.get(url, headers=headers, timeout=15)
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
    except Exception as e:
        print(f"  Page {page} error: {e}")
    
    return items

def scrape_amazon(query: str, max_pages: int = 2) -> list:
    all_items = []
    for page in range(1, max_pages + 1):
        items = scrape_amazon_page(query, page)
        all_items.extend(items)
        print(f"  Page {page}: {len(items)} items")
        time.sleep(random.uniform(0.5, 1))
    return all_items

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
        capacity_gb, capacity_tb = parse_capacity(title)
        if capacity_tb <= 0:
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
        'ssd 1tb', 'ssd 2tb', 'ssd 4tb',
        'hard disk 1tb', 'hard disk 2tb', 'hard disk 4tb',
        'external ssd', 'external hard disk',
        'nvme ssd', 'sata ssd',
    ]
    
    all_products = []
    for query in queries:
        print(f"Scraping: {query}")
        items = scrape_amazon(query, max_pages=2)
        products = process_storage_products(items, 'Amazon.sg')
        all_products.extend(products)
        print(f"  Total: {len(products)}\n")
        time.sleep(random.uniform(0.5, 1))
    
    save_products(all_products)
    print(f"=== Grand total: {len(all_products)} ===")
    return all_products

if __name__ == '__main__':
    scrape_all()
