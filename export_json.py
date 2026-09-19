#!/usr/bin/env python3
"""Export SQLite database to JSON for frontend consumption."""

import sqlite3
import json
import os
from datetime import datetime

from scrape_common import (
    KNOWN_ACCESSORY_ASINS,
    _asin_from_url,
    deactivate_non_storage,
    infer_protocols,
    init_db,
    is_real_storage,
    primary_protocol,
)

DB_PATH = "./diskprices.db"
JSON_PATH = "./data/products.json"

os.makedirs(os.path.dirname(JSON_PATH), exist_ok=True)

def export_to_json():
    # Migrate schema so COALESCE(is_active, 1) / accessory purge work on old DBs.
    init_db()
    conn = sqlite3.connect(DB_PATH)
    deactivated = deactivate_non_storage(conn)
    if deactivated:
        print(f"Deactivated {deactivated} non-storage / known-accessory rows")

    c = conn.cursor()
    c.execute('''
        SELECT platform, title, url, image_url, price, original_price,
               capacity_gb, capacity_tb, is_ssd, cost_per_tb, rating,
               review_count, seller, timestamp
        FROM products
        WHERE COALESCE(is_active, 1) = 1
        ORDER BY capacity_tb DESC, capacity_gb DESC
    ''')
    rows = c.fetchall()

    products = []
    skipped = 0
    for row in rows:
        title = row[1]
        url = row[2]
        asin = _asin_from_url(url)
        if asin in KNOWN_ACCESSORY_ASINS or not is_real_storage(title or ''):
            skipped += 1
            continue
        protocols = infer_protocols(title or '', asin=asin)
        products.append({
            'platform': row[0],
            'title': title,
            'url': url,
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
            'protocols': protocols,
            'protocol': primary_protocol(protocols),
        })

    conn.close()

    last_updated = max((p['timestamp'] for p in products), default=None)

    output = {
        'products': products,
        'lastUpdated': last_updated,
        'exportedAt': datetime.now().isoformat(),
    }

    with open(JSON_PATH, 'w') as f:
        json.dump(output, f, indent=2)

    extra = f" (skipped {skipped} accessory rows at export)" if skipped else ""
    print(f"Exported {len(products)} products to {JSON_PATH}{extra}")

if __name__ == '__main__':
    export_to_json()
