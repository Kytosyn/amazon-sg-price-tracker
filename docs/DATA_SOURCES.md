# DiskPrices data sources

## Primary multi-platform path: official affiliate APIs

Preferred ingest for **Shopee** and **Lazada** is each marketplace’s **official Affiliate Open API** (not HTML scraping, not BuyWhere).

| Platform | Script | Status | Secrets |
| --- | --- | --- | --- |
| **Shopee** | `shopee_affiliate_scraper.py` | Implemented — GraphQL `productOfferV2` on SG Open API | `SHOPEE_AFFILIATE_APP_ID`, `SHOPEE_AFFILIATE_SECRET` |
| **Lazada** | `lazada_affiliate_scraper.py` | Stub until Affiliate product-search docs are available after approval | `LAZADA_AFFILIATE_APP_KEY`, `LAZADA_AFFILIATE_APP_SECRET`, optional `LAZADA_AFFILIATE_ACCESS_TOKEN` |
| **Amazon.sg** | `scraper.py` | HTML via ZenRows / ScraperAPI (or direct) | `ZENROWS_API_KEY` or `SCRAPERAPI_KEY` |

Shared helpers: `scrape_common.py` (`init_db`, `parse_capacity`, `is_ssd`, `is_real_storage`, `process_products`, `save_products`, `STORAGE_QUERIES`).

Setup walkthrough: **[AFFILIATE_SETUP.md](./AFFILIATE_SETUP.md)**.

### Shopee Affiliate (SG)

| Item | Detail |
| --- | --- |
| Endpoint | `POST https://open-api.affiliate.shopee.com.sg/graphql` |
| Auth | `Authorization: SHA256 Credential={appId},Timestamp={ts},Signature={sha256(appId+ts+body+secret)}` |
| Query | `productOfferV2` keyword search over the same HDD/SSD list as Amazon |
| Platform label | `Shopee` |
| Fail behaviour | Exit 1 if secrets missing; exit 1 if 0 storage products when secrets present |

Signup: [affiliate.shopee.sg](https://affiliate.shopee.sg/)

### Lazada Affiliate (SG)

Public pages confirm Lazada Affiliate Program signup and LazOP-style signing on [open.lazada.com](https://open.lazada.com/), but the **affiliate product-search path is not published without portal login**. Seller APIs (`/products/get`, etc. on `https://api.lazada.sg/rest`) are seller-catalog only and are **not** used here.

`lazada_affiliate_scraper.py` exits 1 with apply/TODO instructions until Eddy pastes the confirmed endpoint after approval. Do not HTML-scrape Lazada.

Signup: [lazada.sg/lazada-affiliate-program](https://www.lazada.sg/lazada-affiliate-program)

---

## Amazon.sg HTML path (still required)

`scraper.py` scrapes Amazon.sg search pages into the same `diskprices.db`. Fail-closed: exit 1 if 0 products.

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

## Optional fallback: BuyWhere (PR #7 closed)

BuyWhere (`buywhere_scraper.py`) was explored as a multi-platform catalog API and **rejected** for the primary path — PR **#7** (`feat/buywhere-multi-platform`) was **closed** without merge. It remains an optional future fallback if affiliate APIs are insufficient; do not treat it as the default.

---

## Workflow behaviour

`.github/workflows/scrape.yml`:

1. Always run Amazon (`scraper.py`)
2. Run Shopee if `SHOPEE_AFFILIATE_APP_ID` + `SHOPEE_AFFILIATE_SECRET` are set; otherwise skip with a notice
3. Run Lazada if `LAZADA_AFFILIATE_APP_KEY` + `LAZADA_AFFILIATE_APP_SECRET` are set; otherwise skip with a notice (stub will exit 1 until endpoint is implemented — only enable secrets after docs access)
4. `export_json.py` → commit `diskprices.db` + `data/products.json` when non-empty

## Local refresh

```bash
python scraper.py
# after secrets:
python shopee_affiliate_scraper.py
# python lazada_affiliate_scraper.py   # stub until endpoint wired
python export_json.py
```
