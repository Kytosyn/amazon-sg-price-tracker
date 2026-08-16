-- Database Schema for Amazon.sg Price Tracker
-- SQLite

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
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asin TEXT NOT NULL,
    price REAL NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asin) REFERENCES products(asin)
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    url TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asin TEXT NOT NULL,
    target_price REAL NOT NULL,
    email TEXT,
    discord_webhook TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    triggered BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (asin) REFERENCES products(asin)
);

CREATE TABLE IF NOT EXISTS scrape_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT,
    category TEXT,
    status TEXT DEFAULT 'pending',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    products_found INTEGER DEFAULT 0
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_price_history_asin ON price_history(asin);
CREATE INDEX IF NOT EXISTS idx_price_history_timestamp ON price_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_asin ON products(asin);
CREATE INDEX IF NOT EXISTS idx_alerts_asin ON alerts(asin);
