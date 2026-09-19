# DiskPrices data sources

DiskPrices SG can ingest from **three complementary paths**. All write the same
`diskprices.db` → `export_json.py` → `data/products.json` pipeline via shared
helpers in `scrape_common.py`.

| Path | Script | Status | Secrets |
| --- | --- | --- | --- |
| **Amazon.sg** (HTML) | `scraper.py` | Required — ZenRows / ScraperAPI (or direct) | `ZENROWS_API_KEY` or `SCRAPERAPI_KEY` |
| **BuyWhere** (multi-platform) | `buywhere_scraper.py` | Optional — Shopee / Lazada / Amazon.sg / others | `BUYWHERE_API_KEY` |
| **Shopee Affiliate** | `shopee_affiliate_scraper.py` | Optional — GraphQL `productOfferV2` (SG Open API) | `SHOPEE_AFFILIATE_APP_ID`, `SHOPEE_AFFILIATE_SECRET` |
| **Lazada Affiliate** | `lazada_affiliate_scraper.py` | Stub until Affiliate product-search docs after approval | `LAZADA_AFFILIATE_APP_KEY`, `LAZADA_AFFILIATE_APP_SECRET`, optional `LAZADA_AFFILIATE_ACCESS_TOKEN` |

Shared helpers: `scrape_common.py` (`init_db`, `parse_capacity`, `is_ssd`, `is_real_storage`, `process_products`, `save_products`, `STORAGE_QUERIES`).

Affiliate signup walkthrough: **[AFFILIATE_SETUP.md](./AFFILIATE_SETUP.md)**.

---

## 1. Amazon.sg HTML path (required, fail-closed)

`scraper.py` scrapes Amazon.sg search pages into `diskprices.db`. Fail-closed: exit 1 if 0 products.

### Why GitHub Actions often returns 0 Amazon results

Amazon.sg blocks many datacenter IPs (including GitHub-hosted runners). Direct `requests` scrapes can work from some IPs but return empty/captcha on Actions.

### ScraperAPI or ZenRows

- Create an account at scraperapi.com or zenrows.com
- Add repo secret `SCRAPERAPI_KEY` or `ZENROWS_API_KEY`
- `scraper.py` routes Amazon URLs through the proxy automatically

### Amazon Creators API (official; replaces deprecated PA-API 5)

- Requires Amazon Associates / Creators enrollment for the target marketplace
- Docs: https://affiliate-program.amazon.com/creatorsapi/docs/
- Best long-term compliant Amazon catalog access; more setup than a proxy

---

## 2. BuyWhere (optional multi-platform)

BuyWhere is a catalog API that can return **Shopee**, **Lazada**, **Amazon.sg**, and other SG retailers in one pass. Use it alongside or instead of per-marketplace affiliate credentials when you have a key.

| Item | Detail |
| --- | --- |
| Script | `buywhere_scraper.py` |
| API | `GET https://api.buywhere.ai/v1/products/search` |
| Auth | `Authorization: Bearer $BUYWHERE_API_KEY` |
| Params | `q`, `country_code=SG`, `deliver_to=SG`, `limit`, `sort=price_asc` |
| Platform labels | `Shopee` / `Lazada` / `Amazon.sg` (exact UI strings); other merchants use a readable name |

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

---

## 3. Official affiliate APIs (optional per marketplace)

Preferred official ingest for **Shopee** and **Lazada** when you have affiliate approval (not HTML scraping).

### Shopee Affiliate (SG)

| Item | Detail |
| --- | --- |
| Endpoint | `POST https://open-api.affiliate.shopee.com.sg/graphql` |
| Auth | `Authorization: SHA256 Credential={appId},Timestamp={ts},Signature={sha256(appId+ts+body+secret)}` |
| Query | `productOfferV2` keyword search over the same HDD/SSD list as Amazon |
| Platform label | `Shopee` |
| Fail behaviour | Exit 1 if secrets missing locally; exit 1 if 0 storage products when secrets present |

Signup: [affiliate.shopee.sg](https://affiliate.shopee.sg/)

### Lazada Affiliate (SG)

Public pages confirm Lazada Affiliate Program signup and LazOP-style signing on [open.lazada.com](https://open.lazada.com/), but the **affiliate product-search path is not published without portal login**. Seller APIs (`/products/get`, etc. on `https://api.lazada.sg/rest`) are seller-catalog only and are **not** used here.

`lazada_affiliate_scraper.py` is a structured stub: if `ENDPOINT` is still unset it **exits 0 with a notice** (so CI does not fail when secrets are present but the stub is not yet wired). Do not HTML-scrape Lazada.

Signup: [lazada.sg/lazada-affiliate-program](https://www.lazada.sg/lazada-affiliate-program)

---

## Workflow behaviour

`.github/workflows/scrape.yml`:

1. Always run Amazon (`scraper.py`) — fail-closed
2. Run BuyWhere if `BUYWHERE_API_KEY` is set; otherwise skip with a notice
3. Run Shopee if `SHOPEE_AFFILIATE_APP_ID` + `SHOPEE_AFFILIATE_SECRET` are set; otherwise skip with a notice
4. Run Lazada if `LAZADA_AFFILIATE_APP_KEY` + `LAZADA_AFFILIATE_APP_SECRET` are set; otherwise skip with a notice (stub exits 0 until `ENDPOINT` is implemented)
5. `export_json.py` → commit `diskprices.db` + `data/products.json` when non-empty

## Local refresh

```bash
python scraper.py
# optional paths (after secrets):
# python buywhere_scraper.py
# python shopee_affiliate_scraper.py
# python lazada_affiliate_scraper.py   # stub until endpoint wired
python export_json.py
```
