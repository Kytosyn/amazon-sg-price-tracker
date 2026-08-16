"""
Amazon.sg Price Tracker - Backend
FastAPI + Playwright + SQLite
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
import asyncio
import random
import time
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, Page, Browser
from contextlib import asynccontextmanager

DATABASE_URL = "./prices.db"
AMAZON_SG_BASE = "https://www.amazon.sg"

# Database setup
def init_db():
    conn = sqlite3.connect(DATABASE_URL)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            asin TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            category TEXT,
            image_url TEXT,
            url TEXT NOT NULL,
            current_price REAL,
            original_price REAL,
            rating REAL,
            review_count INTEGER,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asin TEXT NOT NULL,
            price REAL NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asin) REFERENCES products(asin)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            url TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Pydantic models
class Product(BaseModel):
    asin: str
    title: str
    category: Optional[str] = None
    image_url: Optional[str] = None
    url: str
    current_price: Optional[float] = None
    original_price: Optional[float] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None

class PriceAlert(BaseModel):
    asin: str
    target_price: float
    email: Optional[str] = None

# FastAPI app
app = FastAPI(title="Amazon.sg Price Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Scraper class
class AmazonSGScraper:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.playwright = None
    
    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
        )
    
    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def create_page(self) -> Page:
        context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        # Stealth mode
        await page.add_init_script('''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = { runtime: {} };
        ''')
        
        return page
    
    async def scrape_product(self, asin: str) -> Optional[dict]:
        """Scrape a single product page by ASIN"""
        page = await self.create_page()
        url = f"{AMAZON_SG_BASE}/dp/{asin}"
        
        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(random.randint(2000, 4000))
            
            # Check for CAPTCHA
            if await page.query_selector('form[action*="validateCaptcha"]'):
                return None
            
            # Extract product data
            title = await page.query_selector('#productTitle')
            title_text = await title.inner_text() if title else None
            
            price_whole = await page.query_selector('.a-price .a-offscreen')
            price_text = await price_whole.inner_text() if price_whole else None
            current_price = float(price_text.replace('$', '').replace(',', '').strip()) if price_text else None
            
            original_price_elem = await page.query_selector('.a-price.a-text-price .a-offscreen')
            original_price_text = await original_price_elem.inner_text() if original_price_elem else None
            original_price = float(original_price_text.replace('$', '').replace(',', '').strip()) if original_price_text else None
            
            rating_elem = await page.query_selector('#acrPopover .a-icon-alt')
            rating_text = await rating_elem.inner_text() if rating_elem else None
            rating = float(rating_text.split(' ')[0]) if rating_text else None
            
            review_elem = await page.query_selector('#acrCustomerReviewText')
            review_text = await review_elem.inner_text() if review_elem else None
            review_count = int(review_text.replace(',', '').split(' ')[0]) if review_text else None
            
            image_elem = await page.query_selector('#landingImage')
            image_url = await image_elem.get_attribute('src') if image_elem else None
            
            return {
                'asin': asin,
                'title': title_text.strip() if title_text else None,
                'url': url,
                'current_price': current_price,
                'original_price': original_price,
                'rating': rating,
                'review_count': review_count,
                'image_url': image_url,
            }
            
        except Exception as e:
            print(f"Error scraping {asin}: {e}")
            return None
        finally:
            await page.close()
    
    async def scrape_search(self, query: str, max_pages: int = 3) -> List[str]:
        """Scrape search results and return ASINs"""
        page = await self.create_page()
        asins = []
        
        for page_num in range(1, max_pages + 1):
            url = f"{AMAZON_SG_BASE}/s?k={query.replace(' ', '+')}&page={page_num}"
            
            try:
                await page.goto(url, wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(random.randint(2000, 4000))
                
                # Check for CAPTCHA
                if await page.query_selector('form[action*="validateCaptcha"]'):
                    break
                
                # Extract ASINs
                items = await page.query_selector_all('[data-asin]')
                for item in items:
                    asin = await item.get_attribute('data-asin')
                    if asin:
                        asins.append(asin)
                
                # Check for next page
                next_btn = await page.query_selector('.s-pagination-next')
                if not next_btn or await next_btn.get_attribute('aria-disabled') == 'true':
                    break
                    
            except Exception as e:
                print(f"Error on page {page_num}: {e}")
                break
        
        await page.close()
        return asins
    
    async def scrape_category(self, category_url: str) -> List[str]:
        """Scrape a category page"""
        return await self.scrape_search(category_url, max_pages=5)

# Database operations
def save_product(product: dict):
    conn = sqlite3.connect(DATABASE_URL)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO products (asin, title, category, image_url, url, current_price, original_price, rating, review_count, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (
        product['asin'],
        product['title'],
        product.get('category'),
        product.get('image_url'),
        product['url'],
        product.get('current_price'),
        product.get('original_price'),
        product.get('rating'),
        product.get('review_count'),
    ))
    
    # Save price history
    if product.get('current_price'):
        c.execute('INSERT INTO price_history (asin, price) VALUES (?, ?)',
                  (product['asin'], product['current_price']))
    
    conn.commit()
    conn.close()

def get_product(asin: str) -> Optional[dict]:
    conn = sqlite3.connect(DATABASE_URL)
    c = conn.cursor()
    c.execute('SELECT * FROM products WHERE asin = ?', (asin,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return {
            'id': row[0], 'asin': row[1], 'title': row[2], 'category': row[3],
            'image_url': row[4], 'url': row[5], 'current_price': row[6],
            'original_price': row[7], 'rating': row[8], 'review_count': row[9],
            'last_updated': row[10]
        }
    return None

def get_price_history(asin: str, days: int = 30) -> List[dict]:
    conn = sqlite3.connect(DATABASE_URL)
    c = conn.cursor()
    c.execute('''
        SELECT price, timestamp FROM price_history 
        WHERE asin = ? AND timestamp >= datetime('now', ?)
        ORDER BY timestamp ASC
    ''', (asin, f'-{days} days'))
    rows = c.fetchall()
    conn.close()
    
    return [{'price': r[0], 'timestamp': r[1]} for r in rows]

def get_products(category: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[dict]:
    conn = sqlite3.connect(DATABASE_URL)
    c = conn.cursor()
    
    if category:
        c.execute('''
            SELECT * FROM products WHERE category = ?
            ORDER BY last_updated DESC LIMIT ? OFFSET ?
        ''', (category, limit, offset))
    else:
        c.execute('''
            SELECT * FROM products ORDER BY last_updated DESC LIMIT ? OFFSET ?
        ''', (limit, offset))
    
    rows = c.fetchall()
    conn.close()
    
    return [{
        'id': r[0], 'asin': r[1], 'title': r[2], 'category': r[3],
        'image_url': r[4], 'url': r[5], 'current_price': r[6],
        'original_price': r[7], 'rating': r[8], 'review_count': r[9],
        'last_updated': r[10]
    } for r in rows]

def get_deals(min_discount: float = 20.0, limit: int = 50) -> List[dict]:
    """Get products with price drops >= min_discount%"""
    conn = sqlite3.connect(DATABASE_URL)
    c = conn.cursor()
    c.execute('''
        SELECT p.*, 
               (p.original_price - p.current_price) / p.original_price * 100 as discount
        FROM products p
        WHERE p.original_price IS NOT NULL 
          AND p.current_price < p.original_price
          AND (p.original_price - p.current_price) / p.original_price * 100 >= ?
        ORDER BY discount DESC
        LIMIT ?
    ''', (min_discount, limit))
    rows = c.fetchall()
    conn.close()
    
    return [{
        'id': r[0], 'asin': r[1], 'title': r[2], 'category': r[3],
        'image_url': r[4], 'url': r[5], 'current_price': r[6],
        'original_price': r[7], 'rating': r[8], 'review_count': r[9],
        'last_updated': r[10], 'discount': r[11]
    } for r in rows]

def get_categories() -> List[str]:
    conn = sqlite3.connect(DATABASE_URL)
    c = conn.cursor()
    c.execute('SELECT DISTINCT category FROM products WHERE category IS NOT NULL')
    categories = [r[0] for r in c.fetchall()]
    conn.close()
    return categories

# API Endpoints

@app.get("/api/products")
def list_products(category: Optional[str] = None, limit: int = 50, offset: int = 0):
    return get_products(category, limit, offset)

@app.get("/api/products/{asin}")
def get_product_endpoint(asin: str):
    product = get_product(asin)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.get("/api/products/{asin}/history")
def get_product_history(asin: str, days: int = 30):
    return get_price_history(asin, days)

@app.get("/api/deals")
def list_deals(min_discount: float = 20.0, limit: int = 50):
    return get_deals(min_discount, limit)

@app.get("/api/categories")
def list_categories():
    return get_categories()

@app.get("/api/search")
def search_products(q: str, background_tasks: BackgroundTasks):
    """Search Amazon.sg and start scraping results in background"""
    background_tasks.add_task(scrape_search_task, q)
    return {"message": "Search started", "query": q}

@app.get("/api/scrape/{asin}")
def scrape_product_endpoint(asin: str, background_tasks: BackgroundTasks):
    """Start scraping a specific ASIN in background"""
    background_tasks.add_task(scrape_product_task, asin)
    return {"message": "Scraping started", "asin": asin}

@app.get("/api/stats")
def get_stats():
    conn = sqlite3.connect(DATABASE_URL)
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM products')
    total_products = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM price_history')
    total_price_points = c.fetchone()[0]
    
    c.execute('SELECT COUNT(DISTINCT asin) FROM price_history WHERE timestamp >= datetime("now", "-1 day")')
    updated_today = c.fetchone()[0]
    
    conn.close()
    
    return {
        'total_products': total_products,
        'total_price_points': total_price_points,
        'updated_today': updated_today
    }

# Background tasks
async def scrape_product_task(asin: str):
    scraper = AmazonSGScraper()
    await scraper.start()
    try:
        product = await scraper.scrape_product(asin)
        if product:
            save_product(product)
            print(f"Saved: {product['title']}")
    finally:
        await scraper.stop()

async def scrape_search_task(query: str):
    scraper = AmazonSGScraper()
    await scraper.start()
    try:
        asins = await scraper.scrape_search(query, max_pages=2)
        for asin in asins[:10]:  # Limit to first 10 results
            product = await scraper.scrape_product(asin)
            if product:
                save_product(product)
            await asyncio.sleep(random.uniform(2, 5))  # Be respectful
    finally:
        await scraper.stop()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
