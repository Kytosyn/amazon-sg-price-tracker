#!/usr/bin/env python3
"""
DiskPrices Singapore - Multi-Platform HDD/SSD Price Comparison
Scrapes Shopee, Lazada, and Amazon.sg for the best storage deals.
Focuses on cost/TB comparison.
"""

import re
import json
import time
import random
import sqlite3
import requests
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional
from urllib.parse import quote_plus

DB_PATH = "./diskprices.db"

# ─── Data Models ───────────────────────────────────────────────

@dataclass
class StorageProduct:
    platform: str
    title: str
    url: str
    image_url: str
    price: float
    original_price: float
    capacity_gb: float
    capacity_tb: float
    is_ssd: bool
    cost_per_tb: float
    rating: float
    review_count: int
    seller: str
    timestamp: str

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
    
    # Default: if price/capacity ratio suggests SSD
    return False

# ─── Shopee Scraper ────────────────────────────────────────────

class ShopeeScraper:
    BASE_URL = "https://shopee.sg/api/v4/search/search_items"
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://shopee.sg/',
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    def search(self, query: str, limit: int = 50) -> List[dict]:
        """Search Shopee for products."""
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
                price = item_basic.get('price', 0) / 100000  # Shopee price is in cents * 1000
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

# ─── Lazada Scraper ────────────────────────────────────────────

class LazadaScraper:
    """Lazada scraping via their internal API."""
    
    BASE_URL = "https://www.lazada.sg/catalog/"
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.lazada.sg/',
    }
    
    def search(self, query: str, limit: int = 40) -> List[dict]:
        """Search Lazada for products."""
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

# ─── Amazon.sg Scraper ─────────────────────────────────────────

class AmazonSGScraper:
    """Amazon.sg scraping via their search page."""
    
    BASE_URL = "https://www.amazon.sg/s"
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.amazon.sg/',
    }
    
    def search(self, query: str, limit: int = 50) -> List[dict]:
        """Search Amazon.sg for products."""
        params = {
            'k': quote_plus(query),
            'ref': 'nb_sb_noss',
        }
        
        try:
            resp = requests.get(self.BASE_URL, params=params, headers=self.HEADERS, timeout=15)
            resp.raise_for_status()
            
            # Extract data from HTML
            html = resp.text
            
            items = []
            # Find product containers
            import re
            
            # Extract ASINs and data from search results
            asin_pattern = r'data-asin="([A-Z0-9]{10})"'
            asins = re.findall(asin_pattern, html)
            
            # Extract titles
            title_pattern = r'<span class="a-text-normal">([^<]+)</span>'
            titles = re.findall(title_pattern, html)
            
            # Extract prices
            price_pattern = r'class="a-price-whole">(\d+)[^<]*</span><span class="a-price-decimal">'
            prices = re.findall(price_pattern, html)
            
            # Extract image URLs
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

def process_storage_products(items: List[dict], platform: str) -> List[StorageProduct]:
    """Convert raw scraped data into StorageProduct objects."""
    products = []
    
    for item in items:
        title = item.get('title', '')
        price = item.get('price', 0)
        
        if price <= 0:
            continue
        
        # Parse capacity
        capacity_gb, capacity_tb = parse_capacity(title)
        
        if capacity_tb <= 0:
            continue
        
        # Determine SSD vs HDD
        ssd = is_ssd(title)
        
        # Calculate cost per TB
        cost_per_tb = price / capacity_tb
        
        products.append(StorageProduct(
            platform=platform,
            title=title,
            url=item.get('url', ''),
            image_url=item.get('image_url', ''),
            price=price,
            original_price=item.get('original_price', price),
            capacity_gb=capacity_gb,
            capacity_tb=capacity_tb,
            is_ssd=ssd,
            cost_per_tb=cost_per_tb,
            rating=item.get('rating', 0),
            review_count=item.get('review_count', 0),
            seller=item.get('seller', ''),
            timestamp=datetime.now().isoformat(),
        ))
    
    return products

# ─── Database Operations ───────────────────────────────────────

def save_products(products: List[StorageProduct]):
    """Save products to database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    for p in products:
        try:
            c.execute('''
                INSERT OR REPLACE INTO products 
                (platform, title, url, image_url, price, original_price, capacity_gb, capacity_tb, is_ssd, cost_per_tb, rating, review_count, seller, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (p.platform, p.title, p.url, p.image_url, p.price, p.original_price,
                  p.capacity_gb, p.capacity_tb, p.is_ssd, p.cost_per_tb, p.rating,
                  p.review_count, p.seller, p.timestamp))
            
            # Save price history
            c.execute('INSERT INTO price_history (url, price) VALUES (?, ?)', (p.url, p.price))
        except sqlite3.IntegrityError:
            pass  # Duplicate URL
    
    conn.commit()
    conn.close()

def get_products(platform: Optional[str] = None, is_ssd: Optional[bool] = None, 
                 limit: int = 100, sort_by: str = 'cost_per_tb') -> List[dict]:
    """Retrieve products from database."""
    conn = sqlite3.connect(DB_PATH)
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
    """Get database statistics."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM products")
    total = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM products WHERE is_ssd = 1")
    ssd_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM products WHERE is_ssd = 0")
    hdd_count = c.fetchone()[0]
    
    conn.close()
    
    return {'total': total, 'ssd': ssd_count, 'hdd': hdd_count}

# ─── Main Scraper ──────────────────────────────────────────────

def scrape_all():
    """Scrape all platforms for storage products."""
    queries = [
        'ssd 1tb', 'ssd 2tb', 'ssd 4tb',
        'hard disk 1tb', 'hard disk 2tb', 'hard disk 4tb', 'hard disk 8tb',
        'external ssd', 'external hard disk',
        'nvme ssd', 'sata ssd',
    ]
    
    shopee = ShopeeScraper()
    lazada = LazadaScraper()
    amazon = AmazonSGScraper()
    
    all_products = []
    
    for query in queries:
        print(f"Scraping: {query}")
        
        # Shopee
        shopee_items = shopee.search(query, limit=30)
        shopee_products = process_storage_products(shopee_items, 'Shopee')
        all_products.extend(shopee_products)
        print(f"  Shopee: {len(shopee_products)} products")
        
        # Lazada
        lazada_items = lazada.search(query, limit=30)
        lazada_products = process_storage_products(lazada_items, 'Lazada')
        all_products.extend(lazada_products)
        print(f"  Lazada: {len(lazada_products)} products")
        
        # Amazon
        amazon_items = amazon.search(query, limit=30)
        amazon_products = process_storage_products(amazon_items, 'Amazon.sg')
        all_products.extend(amazon_products)
        print(f"  Amazon: {len(amazon_products)} products")
        
        time.sleep(random.uniform(1, 2))
    
    # Save to database
    save_products(all_products)
    print(f"\nTotal products saved: {len(all_products)}")
    
    return all_products

if __name__ == '__main__':
    scrape_all()
