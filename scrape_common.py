#!/usr/bin/env python3
"""Shared DB + storage helpers for Amazon and BuyWhere importers."""

import re
import sqlite3
from datetime import datetime

DB_PATH = "./diskprices.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS products (
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
    )""")
    # Existing checked-in DBs predate first_seen/last_seen/is_active;
    # CREATE TABLE IF NOT EXISTS will not add columns to an old schema.
    cols = {row[1] for row in c.execute("PRAGMA table_info(products)")}
    for name, decl in (
        ("first_seen", "TIMESTAMP"),
        ("last_seen", "TIMESTAMP"),
        ("is_active", "BOOLEAN DEFAULT 1"),
    ):
        if name not in cols:
            c.execute(f"ALTER TABLE products ADD COLUMN {name} {decl}")
            print(f"Migrated products: added column {name}")
    c.execute("""UPDATE products SET first_seen = COALESCE(first_seen, timestamp, CURRENT_TIMESTAMP)
                 WHERE first_seen IS NULL""")
    c.execute("""UPDATE products SET last_seen = COALESCE(last_seen, timestamp, CURRENT_TIMESTAMP)
                 WHERE last_seen IS NULL""")
    c.execute("""UPDATE products SET is_active = COALESCE(is_active, 1)
                 WHERE is_active IS NULL""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_url ON products(url)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_capacity ON products(capacity_tb)")
    conn.commit()
    conn.close()


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


def process_products(items, default_platform='Amazon.sg', default_seller=None):
    """Filter raw items into storage products. Platform/seller may come from item."""
    products = []
    seen = set()
    seller_fallback = default_seller if default_seller is not None else default_platform
    for item in items:
        title = item.get('title', '')
        price = item.get('price', 0) or 0
        url = item.get('url', '')
        if price <= 0 or not url or url in seen:
            continue
        if not is_real_storage(title):
            continue
        cap_gb, cap_tb = parse_capacity(title)
        if cap_tb <= 0:
            continue
        seen.add(url)
        platform = item.get('platform') or default_platform
        seller = item.get('seller') or seller_fallback
        original = item.get('original_price')
        if original is None or original <= 0:
            original = price
        products.append({
            'platform': platform,
            'title': title,
            'url': url,
            'image_url': item.get('image_url', '') or '',
            'price': price,
            'original_price': original,
            'capacity_gb': cap_gb,
            'capacity_tb': cap_tb,
            'is_ssd': is_ssd(title),
            'cost_per_tb': price / cap_tb if cap_tb > 0 else 0,
            'seller': seller,
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
