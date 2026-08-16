#!/usr/bin/env python3
"""
DiskPrices Singapore - Multi-Platform HDD/SSD Price Comparison
Uses requests + BeautifulSoup for faster, more reliable scraping.
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
    
    # Look for TB patterns like "1TB", "2 TB", "4TB", "8TB" but not "TBW"
    tb_match = re.search(r'(\d+(?:\.\d+)?)\s*tb(?!w)', title_lower)
    if tb_match:
        tb = float(tb_match.group(1))
        return tb * 1000, tb
    
    # Look for GB patterns like "256GB", "512 GB" but not "GBW"
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

# ─── Scrapers ──────────────────────────────────────────────────

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

def scrape_shopee(query: str) -> list:
    """Scrape Shopee search results."""
    items = []
    url = f"https://shopee.sg/search?keyword={quote_plus(query)}"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Find product cards
        products = soup.find_all('div', {'data-sqe': 'item'})
        if not products:
            # Try alternative selectors
            products = soup.find_all('a', href=re.compile(r'/product/\d+/\d+'))
        
        for product in products[:30]:
            try:
                # Title
                title_el = product.find('div', {'data-sqe': 'name'}) or product.find('div', class_=re.compile(r'.*name.*'))
                title = title_el.get_text(strip=True) if title_el else ""
                
                # Price
                price_el = product.find('div', {'data-sqe': 'price'}) or product.find('span', class_=re.compile(r'.*price.*'))
                price_text = price_el.get_text(strip=True) if price_el else "0"
                price = float(re.sub(r'[^\d.]', '', price_text))
                
                # URL
                link = product.find('a', href=True)
                href = link['href'] if link else ""
                if href and not href.startswith('http'):
                    href = f"https://shopee.sg{href}"
                
                # Image
                img = product.find('img')
                img_url = img.get('src', '') if img else ""
                
                if title and price > 0:
                    items.append({
                        'title': title,
                        'url': href,
                        'image_url': img_url,
                        'price': price,
                        'original_price': price,
                        'rating': 0,
                        'review_count': 0,
                        'seller': '',
                    })
            except Exception as e:
                continue
    except Exception as e:
        print(f"  Shopee error: {e}")
    
    return items

def scrape_lazada(query: str) -> list:
    """Scrape Lazada search results."""
    items = []
    url = f"https://www.lazada.sg/catalog/?q={quote_plus(query)}"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Find product cards
        products = soup.find_all('div', {'data-tracking': 'product-card'})
        if not products:
            products = soup.find_all('div', class_=re.compile(r'.*pdp-mod-product-badge.*'))
        
        for product in products[:30]:
            try:
                # Title
                title_el = product.find('div', class_=re.compile(r'.*pdp-mod-product-badge-title.*'))
                title = title_el.get_text(strip=True) if title_el else ""
                
                # Price
                price_el = product.find('span', class_=re.compile(r'.*pdp-price.*'))
                price_text = price_el.get_text(strip=True) if price_el else "0"
                price = float(re.sub(r'[^\d.]', '', price_text))
                
                # URL
                link = product.find('a', href=True)
                href = link['href'] if link else ""
                if href and not href.startswith('http'):
                    href = f"https://www.lazada.sg{href}"
                
                # Image
                img = product.find('img')
                img_url = img.get('src', '') if img else ""
                
                if title and price > 0:
                    items.append({
                        'title': title,
                        'url': href,
                        'image_url': img_url,
                        'price': price,
                        'original_price': price,
                        'rating': 0,
                        'review_count': 0,
                        'seller': '',
                    })
            except Exception as e:
                continue
    except Exception as e:
        print(f"  Lazada error: {e}")
    
    return items

def scrape_amazon(query: str) -> list:
    """Scrape Amazon.sg search results."""
    items = []
    url = f"https://www.amazon.sg/s?k={quote_plus(query)}"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Find product cards
        products = soup.find_all('div', {'data-asin': True})
        
        for product in products[:30]:
            try:
                asin = product.get('data-asin')
                if not asin:
                    continue
                
                # Title
                title_el = product.find('h2')
                title = title_el.get_text(strip=True) if title_el else ""
                
                # Price
                price_el = product.find('span', class_='a-price-whole')
                price_text = price_el.get_text(strip=True) if price_el else "0"
                price = float(re.sub(r'[^\d.]', '', price_text))
                
                # Image
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
            except Exception as e:
                continue
    except Exception as e:
        print(f"  Amazon error: {e}")
    
    return items

# ─── Price Processor ───────────────────────────────────────────

def process_storage_products(items: list, platform: str) -> list:
    products = []
    for item in items:
        title = item.get('title', '')
        price = item.get('price', 0)
        if price <= 0:
            continue
        capacity_gb, capacity_tb = parse_capacity(title)
        if capacity_tb <= 0:
            continue
        ssd = is_ssd(title)
        cost_per_tb = price / capacity_tb
        products.append({
            'platform': platform,
            'title': title,
            'url': item.get('url', ''),
            'image_url': item.get('image_url', ''),
            'price': price,
            'original_price': item.get('original_price', price),
            'capacity_gb': capacity_gb,
            'capacity_tb': capacity_tb,
            'is_ssd': ssd,
            'cost_per_tb': cost_per_tb,
            'rating': item.get('rating', 0),
            'review_count': item.get('review_count', 0),
            'seller': item.get('seller', ''),
            'timestamp': datetime.now().isoformat(),
        })
    return products

# ─── Database Operations ───────────────────────────────────────

def save_products(products: list):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for p in products:
        try:
            c.execute('''
                INSERT OR REPLACE INTO products 
                (platform, title, url, image_url, price, original_price, capacity_gb, capacity_tb, is_ssd, cost_per_tb, rating, review_count, seller, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (p['platform'], p['title'], p['url'], p['image_url'], p['price'], p['original_price'],
                  p['capacity_gb'], p['capacity_tb'], p['is_ssd'], p['cost_per_tb'], p['rating'],
                  p['review_count'], p['seller'], p['timestamp']))
            c.execute('INSERT INTO price_history (url, price) VALUES (?, ?)', (p['url'], p['price']))
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()

# ─── Main Scraper ──────────────────────────────────────────────

def scrape_all():
    queries = [
        'ssd 1tb', 'ssd 2tb', 'ssd 4tb',
        'hard disk 1tb', 'hard disk 2tb', 'hard disk 4tb', 'hard disk 8tb',
        'external ssd', 'external hard disk',
        'nvme ssd', 'sata ssd',
    ]
    
    all_products = []
    
    for query in queries:
        print(f"Scraping: {query}")
        
        # Shopee
        shopee_items = scrape_shopee(query)
        shopee_products = process_storage_products(shopee_items, 'Shopee')
        all_products.extend(shopee_products)
        print(f"  Shopee: {len(shopee_products)} products")
        
        # Lazada
        lazada_items = scrape_lazada(query)
        lazada_products = process_storage_products(lazada_items, 'Lazada')
        all_products.extend(lazada_products)
        print(f"  Lazada: {len(lazada_products)} products")
        
        # Amazon
        amazon_items = scrape_amazon(query)
        amazon_products = process_storage_products(amazon_items, 'Amazon.sg')
        all_products.extend(amazon_products)
        print(f"  Amazon: {len(amazon_products)} products")
        
        time.sleep(random.uniform(0.5, 1.5))
    
    save_products(all_products)
    print(f"\nTotal products saved: {len(all_products)}")
    return all_products

if __name__ == '__main__':
    scrape_all()
