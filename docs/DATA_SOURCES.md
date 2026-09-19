# DiskPrices data sources

## Why GitHub Actions often returns 0 Amazon results
Amazon.sg blocks many datacenter IPs (including GitHub-hosted runners). Direct `requests` scrapes can work from some IPs but return empty/captcha on Actions.

## Recommended API paths (pick one)

### 1) ScraperAPI or ZenRows (fastest unblock for current scraper)
- Create an account at scraperapi.com or zenrows.com
- Add repo secret `SCRAPERAPI_KEY` or `ZENROWS_API_KEY`
- `scraper.py` routes Amazon URLs through the proxy automatically

### 2) Amazon Creators API (official; replaces deprecated PA-API 5)
- Requires Amazon Associates / Creators enrollment for the target marketplace
- Docs: https://affiliate-program.amazon.com/creatorsapi/docs/
- Best long-term compliant catalog access; more setup than a proxy

### 3) Keepa / Rainforest API
- Keepa: strong price history
- Rainforest: live Amazon product/search JSON
- Add as a dedicated importer if you prefer structured APIs over HTML

### 4) SEA catalog APIs (e.g. BuyWhere)
- Useful when expanding beyond Amazon.sg to Shopee/Lazada

## Local refresh
From a non-blocked IP: `python scraper.py && python export_json.py`, then commit `diskprices.db` + `data/products.json`.
