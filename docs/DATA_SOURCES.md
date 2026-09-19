# DiskPrices data sources

## Primary multi-platform path: BuyWhere

BuyWhere is the preferred way to ingest **Shopee**, **Lazada**, **Amazon.sg**, and other SG retailers into the same SQLite → `export_json.py` → `data/products.json` pipeline.

| Item | Detail |
| --- | --- |
| Script | `buywhere_scraper.py` |
| API | `GET https://api.buywhere.ai/v1/products/search` |
| Auth | `Authorization: Bearer $BUYWHERE_API_KEY` |
| Params | `q`, `country_code=SG`, `deliver_to=SG`, `limit`, `sort=price_asc` |
| Platform labels | `Shopee` / `Lazada` / `Amazon.sg` (exact UI strings); other merchants use a readable name (gray badge OK) |

### Adding the secret

1. Get a key from [BuyWhere quickstart](https://buywhere.ai/quickstart)
2. GitHub repo → **Settings → Secrets and variables → Actions** → New repository secret
3. Name: `BUYWHERE_API_KEY` · Value: your `bw_live_…` key
4. Re-run the **Scrape Disk Prices** workflow (or wait for the schedule)

If the secret is empty/missing, the workflow **skips** BuyWhere with a notice and continues (Amazon fail-closed still applies). Locally, missing key exits with code 1 and a clear message.

### Local spike

```bash
export BUYWHERE_API_KEY=bw_live_...
python buywhere_scraper.py && python export_json.py
```

Shared helpers live in `scrape_common.py` (`init_db`, capacity/SSD filters, `save_products`).

---

## Why GitHub Actions often returns 0 Amazon results

Amazon.sg blocks many datacenter IPs (including GitHub-hosted runners). Direct `requests` scrapes can work from some IPs but return empty/captcha on Actions.

## Amazon.sg HTML path (still supported)

`scraper.py` scrapes Amazon.sg search pages and writes the same `diskprices.db`. Fail-closed: exit 1 if 0 products.

### ScraperAPI or ZenRows (unblock Amazon on Actions)

- Create an account at scraperapi.com or zenrows.com
- Add repo secret `SCRAPERAPI_KEY` or `ZENROWS_API_KEY`
- `scraper.py` routes Amazon URLs through the proxy automatically

### Amazon Creators API (official; replaces deprecated PA-API 5)

- Requires Amazon Associates / Creators enrollment for the target marketplace
- Docs: https://affiliate-program.amazon.com/creatorsapi/docs/
- Best long-term compliant catalog access; more setup than a proxy

### Keepa / Rainforest API

- Keepa: strong price history
- Rainforest: live Amazon product/search JSON
- Add as a dedicated importer if you prefer structured APIs over HTML

## Local refresh (Amazon only)

From a non-blocked IP: `python scraper.py && python export_json.py`, then commit `diskprices.db` + `data/products.json` if desired.
