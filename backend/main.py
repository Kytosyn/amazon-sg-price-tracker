"""
DiskPrices Singapore - Multi-Platform HDD/SSD Price Comparison API
FastAPI + SQLite
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import asyncio
import random
import time
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser
import re
import requests
from urllib.parse import quote_plus

DATABASE_URL = "./diskprices.db"
AMAZON_SG_BASE = "https://www.amazon.sg"

# ─── Database Setup ────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DATABASE_URL)
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
    """Extract capacity in GB and TB from product title."""
    title_lower = title.lower()
    
    # Check for TB
    tb_match = re.search(r'(\d+(?:\.\d+)?)\s*tb', title_lower)
    if tb_match:
        tb = float(tb_match.group(1))
        return tb * 1000, tb
    
    # Check for GB
    gb_match = re.search(r'(\d+(?:\.\d+)?)\s*gb', title_lower)
    if gb_match:
        gb = float(gb_match.group(1))
        return gb, gb / 1000
    
    return 0, 0

def is_ssd(title: str) -> bool:
    """Determine if product is SSD or HDD."""
    title_lower = title.lower()
    ssd_keywords = ['ssd', 'solid state', 'nvme', 'm.2', 'pcie']
    hdd_keywords = ['hdd', 'hard drive', 'hard disk', 'mechanical', 'desktop drive']
    
    for kw in ssd_keywords:
        if kw in title_lower:
            return True
    for kw in hdd_keywords:
        if kw in title_lower:
            return False
    
    return False

# ─── Scrapers ──────────────────────────────────────────────────

class ShopeeScraper:
    BASE_URL = "https://shopee.sg/api/v4/search/search_items"
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://shopee.sg/',
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    def search(self, query: str, limit: int = 50) -> List[dict]:
        params = {
            'by': 'relevancy',
            'keyword': quote_plus(query),
            'limit': limit,
            'newest': 0,
            'order': 'desc',
            'page_type': 'search',
            'version': '2',
        }
        
        try:
            resp = requests.get(self.BASE_URL, params=params, headers=self.HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            items = []
            for item in data.get('items', []):
                item_basic = item.get('itembasic', {})
                price = item_basic.get('price', 0) / 100000
                original_price = item_basic.get('original_price', 0) / 100000 or price
                
                items.append({
                    'title': item_basic.get('name', ''),
                    'url': f"https://shopee.sg/product/{item_basic.get('shopid')}/{item_basic.get('itemid')}",
                    'image_url': f"https://cf.shopee.sg/file/{item_basic.get('image', '')}",
                    'price': price,
                    'original_price': original_price,
                    'rating': item_basic.get('item_rating', {}).get('rating_star', 0),
                    'review_count': item_basic.get('item_rating', {}).get('rating_count', [0])[0],
                    'seller': item_basic.get('shop_name', ''),
                })
            
            return items
        except Exception as e:
            print(f"Shopee search error: {e}")
            return []

class LazadaScraper:
    BASE_URL = "https://www.lazada.sg/catalog/"
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.lazada.sg/',
    }
    
    def search(self, query: str, limit: int = 40) -> List[dict]:
        params = {
            'q': quote_plus(query),
            'from': 'wangpu',
            'langFlag': 'en',
            'page': '1',
            'pageSize': str(limit),
        }
        
        try:
            resp = requests.get(self.BASE_URL, params=params, headers=self.HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            items = []
            for item in data.get('mods', {}).get('listItems', []):
                price = float(item.get('price', 0))
                original_price = float(item.get('originalPrice', 0)) or price
                
                items.append({
                    'title': item.get('name', ''),
                    'url': f"https://www.lazada.sg{item.get('productUrl', '')}",
                    'image_url': item.get('image', ''),
                    'price': price,
                    'original_price': original_price,
                    'rating': float(item.get('ratingScore', 0)),
                    'review_count': int(item.get('review', 0)),
                    'seller': item.get('sellerName', ''),
                })
            
            return items
        except Exception as e:
            print(f"Lazada search error: {e}")
            return []

class AmazonSGScraper:
    BASE_URL = "https://www.amazon.sg/s"
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.amazon.sg/',
    }
    
    def search(self, query: str, limit: int = 50) -> List[dict]:
        params = {
            'k': quote_plus(query),
            'ref': 'nb_sb_noss',
        }
        
        try:
            resp = requests.get(self.BASE_URL, params=params, headers=self.HEADERS, timeout=15)
            resp.raise_for_status()
            
            html = resp.text
            items = []
            
            asin_pattern = r'data-asin="([A-Z0-9]{10})"'
            asins = re.findall(asin_pattern, html)
            
            title_pattern = r'<span class="a-text-normal">([^<]+)</span>'
            titles = re.findall(title_pattern, html)
            
            price_pattern = r'class="a-price-whole">(\d+)[^<]*</span><span class="a-price-decimal">'
            prices = re.findall(price_pattern, html)
            
            img_pattern = r'src="([^"]+\.jpg)"[^>]*class="s-image"'
            images = re.findall(img_pattern, html)
            
            for i, asin in enumerate(asins[:limit]):
                price = float(prices[i]) if i < len(prices) else 0
                items.append({
                    'title': titles[i].strip() if i < len(titles) else '',
                    'url': f"https://www.amazon.sg/dp/{asin}",
                    'image_url': images[i] if i < len(images) else '',
                    'price': price,
                    'original_price': price,
                    'rating': 0,
                    'review_count': 0,
                    'seller': 'Amazon.sg',
                })
            
            return items
        except Exception as e:
            print(f"Amazon search error: {e}")
            return []

# ─── Price Processor ───────────────────────────────────────────

def process_storage_products(items: List[dict], platform: str) -> List[dict]:
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

def save_products(products: List[dict]):
    conn = sqlite3.connect(DATABASE_URL)
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

def get_products(platform: Optional[str] = None, is_ssd: Optional[bool] = None, 
                 limit: int = 100, sort_by: str = 'cost_per_tb') -> List[dict]:
    conn = sqlite3.connect(DATABASE_URL)
    c = conn.cursor()
    
    query = "SELECT * FROM products WHERE 1=1"
    params = []
    
    if platform:
        query += " AND platform = ?"
        params.append(platform)
    
    if is_ssd is not None:
        query += " AND is_ssd = ?"
        params.append(is_ssd)
    
    if sort_by == 'cost_per_tb':
        query += " ORDER BY cost_per_tb ASC"
    elif sort_by == 'price':
        query += " ORDER BY price ASC"
    elif sort_by == 'capacity':
        query += " ORDER BY capacity_tb DESC"
    
    query += " LIMIT ?"
    params.append(limit)
    
    c.execute(query, params)
    rows = c.fetchall()
    
    conn.close()
    
    return [{
        'id': r[0], 'platform': r[1], 'title': r[2], 'url': r[3],
        'image_url': r[4], 'price': r[5], 'original_price': r[6],
        'capacity_gb': r[7], 'capacity_tb': r[8], 'is_ssd': bool(r[9]),
        'cost_per_tb': r[10], 'rating': r[11], 'review_count': r[12],
        'seller': r[13], 'timestamp': r[14]
    } for r in rows]

def get_stats() -> dict:
    conn = sqlite3.connect(DATABASE_URL)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM products")
    total = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM products WHERE is_ssd = 1")
    ssd_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM products WHERE is_ssd = 0")
    hdd_count = c.fetchone()[0]
    
    conn.close()
    
    return {'total': total, 'ssd': ssd_count, 'hdd': hdd_count}

# ─── FastAPI App ───────────────────────────────────────────────

app = FastAPI(title="DiskPrices Singapore API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API Endpoints ─────────────────────────────────────────────

@app.get("/api/diskprices")
def list_diskprices(
    platform: Optional[str] = None,
    is_ssd: Optional[bool] = None,
    limit: int = 100,
    sort_by: str = 'cost_per_tb'
):
    """List all disk prices with optional filters."""
    return get_products(platform, is_ssd, limit, sort_by)

@app.get("/api/diskprices/stats")
def get_diskprices_stats():
    """Get statistics about stored products."""
    return get_stats()

@app.get("/api/diskprices/search")
def search_diskprices(q: str, background_tasks: BackgroundTasks):
    """Search all platforms and start scraping in background."""
    background_tasks.add_task(scrape_all_platforms, q)
    return {"message": "Search started", "query": q}

@app.post("/api/diskprices/scrape")
def trigger_scrape(background_tasks: BackgroundTasks):
    """Trigger a full scrape of all platforms."""
    background_tasks.add_task(scrape_all_platforms_all_queries)
    return {"message": "Full scrape started"}

# ─── Background Tasks ──────────────────────────────────────────

def scrape_all_platforms(query: str):
    """Scrape all platforms for a specific query."""
    shopee = ShopeeScraper()
    lazada = LazadaScraper()
    amazon = AmazonSGScraper()
    
    all_products = []
    
    # Shopee
    shopee_items = shopee.search(query, limit=30)
    all_products.extend(process_storage_products(shopee_items, 'Shopee'))
    
    # Lazada
    lazada_items = lazada.search(query, limit=30)
    all_products.extend(process_storage_products(lazada_items, 'Lazada'))
    
    # Amazon
    amazon_items = amazon.search(query, limit=30)
    all_products.extend(process_storage_products(amazon_items, 'Amazon.sg'))
    
    save_products(all_products)
    print(f"Scraped {len(all_products)} products for: {query}")

def scrape_all_platforms_all_queries():
    """Scrape all platforms for all storage-related queries."""
    queries = [
        'ssd 1tb', 'ssd 2tb', 'ssd 4tb',
        'hard disk 1tb', 'hard disk 2tb', 'hard disk 4tb', 'hard disk 8tb',
        'external ssd', 'external hard disk',
        'nvme ssd', 'sata ssd',
    ]
    
    for query in queries:
        scrape_all_platforms(query)
        time.sleep(random.uniform(1, 2))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
