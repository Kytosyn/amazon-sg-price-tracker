#!/usr/bin/env python3
"""Export SQLite database to JSON for frontend consumption."""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = "./diskprices.db"
JSON_PATH = "./data/products.json"

# Ensure data directory exists
os.makedirs(os.path.dirname(JSON_PATH), exist_ok=True)

def export_to_json():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        SELECT platform, title, url, image_url, price, original_price, 
               capacity_gb, capacity_tb, is_ssd, cost_per_tb, rating, 
               review_count, seller, timestamp 
        FROM products 
        ORDER BY cost_per_tb ASC
    ''')
    rows = c.fetchall()
    
    products = []
    for row in rows:
        products.append({
            'platform': row[0],
            'title': row[1],
            'url': row[2],
            'image_url': row[3],
            'price': row[4],
            'original_price': row[5],
            'capacity_gb': row[6],
            'capacity_tb': row[7],
            'is_ssd': bool(row[8]),
            'cost_per_tb': row[9],
            'rating': row[10],
            'review_count': row[11],
            'seller': row[12],
            'timestamp': row[13],
        })
    
    # Get the most recent timestamp
    last_updated = max((p['timestamp'] for p in products), default=None)
    
    output = {
        'products': products,
        'lastUpdated': last_updated,
        'exportedAt': datetime.now().isoformat(),
    }
    
    with open(JSON_PATH, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"Exported {len(products)} products to {JSON_PATH}")

if __name__ == '__main__':
    export_to_json()
