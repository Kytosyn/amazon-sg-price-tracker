# DiskPrices data sources

DiskPrices SG ingests into the same `diskprices.db` → `export_json.py` →
`data/products.json` pipeline via shared helpers in `scrape_common.py`.

| Path | Script | Status | Secrets |
| --- | --- | --- | --- |
| **Amazon.sg** (HTML) | `scraper.py` | **Required** — ZenRows / ScraperAPI (or direct); hard fail-closed | `ZENROWS_API_KEY` or `SCRAPERAPI_KEY` |
| **Shopee.sg** (search JSON via ZenRows) | `shopee_scraper.py` | **Primary SEA** — public `/api/v4/search/search_items` through ZenRows | `ZENROWS_API_KEY` (same as Amazon) |
| **Lazada.sg** (catalog ajax via ZenRows) | `lazada_scraper.py` | **Primary SEA** — `/catalog/?q=…&ajax=true` through ZenRows | `ZENROWS_API_KEY` (same as Amazon) |
| **BuyWhere** (multi-platform) | `buywhere_scraper.py` | **Parked / broken** — Eddy: BuyWhere is dead; kept as optional skip | `BUYWHERE_API_KEY` |
| **Shopee Affiliate** | `shopee_affiliate_scraper.py` | **Parked / dead end** — official GraphQL stalled; optional skip | `SHOPEE_AFFILIATE_APP_ID`, `SHOPEE_AFFILIATE_SECRET` |
| **Lazada Affiliate** | `lazada_affiliate_scraper.py` | **Parked stub** — Affiliate product-search docs gated; optional skip | `LAZADA_AFFILIATE_APP_KEY`, `LAZADA_AFFILIATE_APP_SECRET`, optional `LAZADA_AFFILIATE_ACCESS_TOKEN` |

Shared helpers: `scrape_common.py` (`init_db`, `parse_capacity`, `is_ssd`,
`is_real_storage`, `process_products`, `save_products`, `STORAGE_QUERIES`,
`proxied_url`, `zenrows_get`, `sea_soft_exit`).

Affiliate signup walkthrough (parked): **[AFFILIATE_SETUP.md](./AFFILIATE_SETUP.md)**.

---

## 1. Amazon.sg HTML path (required, hard fail-closed)

`scraper.py` scrapes Amazon.sg search pages into `diskprices.db`. Exit 1 if 0 products.

### Why GitHub Actions often returns 0 Amazon results

Amazon.sg blocks many datacenter IPs (including GitHub-hosted runners). Direct
`requests` scrapes can work from some IPs but return empty/captcha on Actions.

### ScraperAPI or ZenRows

- Create an account at scraperapi.com or zenrows.com
- Add repo secret `SCRAPERAPI_KEY` or `ZENROWS_API_KEY`
- `scrape_common.proxied_url` / `zenrows_get` route URLs through the proxy
  (`premium_proxy=true` for ZenRows — same helper used by Shopee/Lazada)

### Amazon Creators API (official; replaces deprecated PA-API 5)

- Requires Amazon Associates / Creators enrollment for the target marketplace
- Docs: https://affiliate-program.amazon.com/creatorsapi/docs/
- Best long-term compliant Amazon catalog access; more setup than a proxy

---

## 2. Shopee.sg + Lazada.sg via ZenRows (primary multi-platform path)

BuyWhere and the official Shopee/Lazada affiliate Open APIs are **parked /
dead ends** for now. The working SEA path is scraping public search JSON
**only through ZenRows** (no direct unofficial mobile API from Actions IPs).

### Shopee (`shopee_scraper.py`)

| Item | Detail |
| --- | --- |
| Endpoint | `GET https://shopee.sg/api/v4/search/search_items?keyword=…&limit=60&newest=0&by=relevancy&order=desc&page_type=search&scenario=PAGE_GLOBAL_SEARCH&version=2` |
| Proxy | ZenRows `premium_proxy=true` via `zenrows_get` |
| Mapping | `item_basic.name` / `price` (÷100000 → SGD) / image key / `i.{shopid}.{itemid}` URL |
| Platform label | `Shopee` |
| Filters | `is_real_storage` + `parse_capacity` over `STORAGE_QUERIES` |
| Fail behaviour | Soft-fail first week: log `ERROR`, exit 0 (`SEA_SOFT_FAIL=1` default). Set `SEA_SOFT_FAIL=0` to harden to exit 1. |

### Lazada (`lazada_scraper.py`)

| Item | Detail |
| --- | --- |
| Endpoint | `GET https://www.lazada.sg/catalog/?q=…&ajax=true&page=1` (falls back to ZenRows `js_render` if ajax body is not JSON) |
| Proxy | Same ZenRows key / `zenrows_get` |
| Mapping | `mods.listItems[]` → `name`, `price`/`priceShow`, `productUrl`, `image` |
| Platform label | `Lazada` |
| Fail behaviour | Same soft-fail as Shopee |

### Soft vs hard fail (first week)

- **Amazon**: hard fail — empty scrape aborts the job (no empty commit).
- **Shopee / Lazada**: soft fail — each platform logs `ERROR` and exits 0;
  workflow steps also use `continue-on-error: true` so one SEA failure does not
  block the other or the Amazon-backed export. After the first week is stable,
  set `SEA_SOFT_FAIL=0` (and/or drop `continue-on-error`) to harden.

### Local spike

```bash
export ZENROWS_API_KEY=...
export SEA_SOFT_FAIL=0   # optional: hard-fail locally while debugging
python shopee_scraper.py
python lazada_scraper.py
python export_json.py
```

If the key exists only as a GitHub Actions secret, dispatch **Scrape Disk Prices**
on the PR branch / after merge to verify live results.

---

## 3. BuyWhere (parked / broken)

Eddy reports BuyWhere is dead. `buywhere_scraper.py` remains in the repo and
workflow as an **optional skip** when `BUYWHERE_API_KEY` is unset. Do not rely
on it for Shopee/Lazada coverage.

| Item | Detail |
| --- | --- |
| Script | `buywhere_scraper.py` |
| API | `GET https://api.buywhere.ai/v1/products/search` |
| Auth | `Authorization: Bearer $BUYWHERE_API_KEY` |

---

## 4. Official affiliate APIs (parked / dead ends)

Preferred long-term if credentials and product-search access return, but
currently stalled for DiskPrices SG.

### Shopee Affiliate (SG)

| Item | Detail |
| --- | --- |
| Endpoint | `POST https://open-api.affiliate.shopee.com.sg/graphql` |
| Query | `productOfferV2` |
| Status | Parked — workflow skips unless secrets are set |

Signup: [affiliate.shopee.sg](https://affiliate.shopee.sg/)

### Lazada Affiliate (SG)

`lazada_affiliate_scraper.py` remains a stub (`ENDPOINT is None` → exit 0).
Seller LazOP catalog APIs are **not** used.

Signup: [lazada.sg/lazada-affiliate-program](https://www.lazada.sg/lazada-affiliate-program)

---

## Workflow behaviour

`.github/workflows/scrape.yml`:

1. Always run Amazon (`scraper.py`) — **hard** fail-closed
2. If `ZENROWS_API_KEY` set: run `shopee_scraper.py` then `lazada_scraper.py`
   (`SEA_SOFT_FAIL=1`, `continue-on-error: true`)
3. Optionally run BuyWhere / Shopee Affiliate / Lazada Affiliate when their
   secrets are set (otherwise skip with a notice — parked paths)
4. `export_json.py` → commit `diskprices.db` + `data/products.json` when non-empty

## Local refresh

```bash
export ZENROWS_API_KEY=...
python scraper.py
python shopee_scraper.py
python lazada_scraper.py
# parked (optional):
# python buywhere_scraper.py
# python shopee_affiliate_scraper.py
# python lazada_affiliate_scraper.py
python export_json.py
```
