#!/usr/bin/env python3
"""
DiskPrices Singapore - Multi-Platform HDD/SSD Price Comparison
Uses Playwright for headless browser scraping to bypass anti-bot measures.
"""

import re
import time
import random
import sqlite3
from datetime import datetime
from playwright.sync_api import sync_playwright, Page

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
    tb_match = re.search(r'(\d+(?:\.\d+)?)\s*tb', title_lower)
    if tb_match:
        tb = float(tb_match.group(1))
        return tb * 1000, tb
    gb_match = re.search(r'(\d+(?:\.\d+)?)\s*gb', title_lower)
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

def scrape_shopee(query: str, page: Page) -> list:
    """Scrape Shopee search results."""
    items = []
    url = f"https://shopee.sg/search?keyword={query.replace(' ', '%20')}"
    
    try:
        page.goto(url, wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(random.randint(2000, 4000))
        
        # Check for CAPTCHA
        if page.query_selector('text=Verify'):
            print("  Shopee CAPTCHA detected")
            return items
        
        # Extract product data
        products = page.query_selector_all('[data-sqe="item"]')
        for product in products[:30]:
            try:
                title_el = product.query_selector('[data-sqe="name"]')
                title = title_el.inner_text() if title_el else ""
                
                price_el = product.query_selector('[data-sqe="price"]')
                price_text = price_el.inner_text() if price_el else "0"
                price = float(re.sub(r'[^\d.]', '', price_text))
                
                link_el = product.query_selector('a')
                href = link_el.get_attribute('href') if link_el else ""
                if href and not href.startswith('http'):
                    href = f"https://shopee.sg{href}"
                
                img_el = product.query_selector('img')
                img_url = img_el.get_attribute('src') if img_el else ""
                
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

def scrape_lazada(query: str, page: Page) -> list:
    """Scrape Lazada search results."""
    items = []
    url = f"https://www.lazada.sg/catalog/?q={query.replace(' ', '%20')}"
    
    try:
        page.goto(url, wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(random.randint(2000, 4000))
        
        # Check for CAPTCHA
        if page.query_selector('text=Verify'):
            print("  Lazada CAPTCHA detected")
            return items
        
        # Extract product data
        products = page.query_selector_all('[data-tracking="product-card"]')
        for product in products[:30]:
            try:
                title_el = product.query_selector('.pdp-mod-product-badge-title')
                title = title_el.inner_text() if title_el else ""
                
                price_el = product.query_selector('.pdp-price')
                price_text = price_el.inner_text() if price_el else "0"
                price = float(re.sub(r'[^\d.]', '', price_text))
                
                link_el = product.query_selector('a')
                href = link_el.get_attribute('href') if link_el else ""
                if href and not href.startswith('http'):
                    href = f"https://www.lazada.sg{href}"
                
                img_el = product.query_selector('img')
                img_url = img_el.get_attribute('src') if img_el else ""
                
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

def scrape_amazon(query: str, page: Page) -> list:
    """Scrape Amazon.sg search results."""
    items = []
    url = f"https://www.amazon.sg/s?k={query.replace(' ', '+')}"
    
    try:
        page.goto(url, wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(random.randint(2000, 4000))
        
        # Check for CAPTCHA
        if page.query_selector('form[action*="validateCaptcha"]'):
            print("  Amazon CAPTCHA detected")
            return items
        
        # Extract product data
        products = page.query_selector_all('[data-asin]')
        for product in products[:30]:
            try:
                asin = product.get_attribute('data-asin')
                if not asin:
                    continue
                
                title_el = product.query_selector('h2')
                title = title_el.inner_text() if title_el else ""
                
                price_el = product.query_selector('.a-price .a-offscreen')
                price_text = price_el.inner_text() if price_el else "0"
                price = float(re.sub(r'[^\d.]', '', price_text))
                
                img_el = product.query_selector('.s-image')
                img_url = img_el.get_attribute('src') if img_el else ""
                
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
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        all_products = []
        
        for query in queries:
            print(f"Scraping: {query}")
            
            # Shopee
            shopee_items = scrape_shopee(query, page)
            shopee_products = process_storage_products(shopee_items, 'Shopee')
            all_products.extend(shopee_products)
            print(f"  Shopee: {len(shopee_products)} products")
            
            # Lazada
            lazada_items = scrape_lazada(query, page)
            lazada_products = process_storage_products(lazada_items, 'Lazada')
            all_products.extend(lazada_products)
            print(f"  Lazada: {len(lazada_products)} products")
            
            # Amazon
            amazon_items = scrape_amazon(query, page)
            amazon_products = process_storage_products(amazon_items, 'Amazon.sg')
            all_products.extend(amazon_products)
            print(f"  Amazon: {len(amazon_products)} products")
            
            time.sleep(random.uniform(1, 2))
        
        browser.close()
    
    save_products(all_products)
    print(f"\nTotal products saved: {len(all_products)}")
    return all_products

if __name__ == '__main__':
    scrape_all()
