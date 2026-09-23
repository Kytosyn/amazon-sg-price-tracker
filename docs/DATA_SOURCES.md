# DiskPrices data sources

DiskPrices SG ingests into the same `diskprices.db` → `export_json.py` →
`data/products.json` pipeline via shared helpers in `scrape_common.py`.

| Path | Script | Status | Secrets |
| --- | --- | --- | --- |
| **Amazon.sg** (HTML) | `scraper.py` | **Required** — ZenRows / ScraperAPI (or direct); hard fail-closed | `ZENROWS_API_KEY` or `SCRAPERAPI_KEY` |
| **Shopee.sg** (Apify Actor; ZenRows optional) | `shopee_scraper.py` | **Primary SEA** — Apify `lergassy/shopee-scraper` when `APIFY_TOKEN` set; ZenRows HTML/XHR fallback | `APIFY_TOKEN` (preferred); optional `ZENROWS_API_KEY` |
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

## 2. Shopee.sg (Apify) + Lazada.sg (ZenRows)

BuyWhere and the official Shopee/Lazada affiliate Open APIs are **parked /
dead ends** for now. Shopee prefers Apify; Lazada still uses ZenRows.

### Shopee (`shopee_scraper.py`) — Apify default

| Item | Detail |
| --- | --- |
| Provider | `SHOPEE_PROVIDER=auto` (default): **Apify** if `APIFY_TOKEN` set, else ZenRows if `ZENROWS_API_KEY`. Force with `apify` / `zenrows`. |
| Actor | `lergassy/shopee-scraper` (API id `lergassy~shopee-scraper`) |
| Input | `{ mode: "search", country: "SG", searchTerms: SEA_QUERIES, maxItems: N, enrichProducts: false }` |
| Cap | `APIFY_SHOPEE_MAX_ITEMS` (default **100**, hard max 200). Same `SEA_QUERIES` list as before; Actor distributes under the total cap. |
| Cost | Spike run `eYXIMez1kh3nCa6gd` (2026-09-24): **~$0.01/item** ($0.46 / 50 items). Cron is `*/30` — keep the cap low or leave pause vars on until spend is acceptable. |
| Mapping | `title`, `price` (**integer SGD cents ÷ 100**), `originalPrice`, `url`, `shopId`/`itemId`, `imageUrl` → existing product dict for `process_products` / `save_products` |
| Platform label | `Shopee` |
| Filters | `is_real_storage` + `parse_capacity` |
| Fail behaviour | Soft-fail: log `ERROR`, exit 0 (`SEA_SOFT_FAIL=1` default). Apify errors / 0 products soft-exit; Amazon stays hard-fail. |
| Pause exception | When `ZENROWS_PAUSED`/`SCRAPE_PAUSED` is true but `APIFY_TOKEN` is set, **Shopee Apify still runs**; Amazon/Lazada stay skipped. |

#### ZenRows fallback (optional)

| Item | Detail |
| --- | --- |
| When | `SHOPEE_PROVIDER=zenrows`, or `auto` without `APIFY_TOKEN` |
| Endpoint (primary) | `GET https://shopee.sg/search?keyword=…` via ZenRows `js_render` + `premium_proxy` + `proxy_country=sg` + `wait=5000` + `json_response` + `custom_headers` — parse captured `search_items` XHR |
| Endpoint (probe) | `GET https://shopee.sg/api/v4/search/search_items?…` with `premium_proxy` + `proxy_country=sg` + `custom_headers` only (no `js_render` / `mode=auto`) |
| Mapping | `item_basic.name` / `price` (÷100000 micros → SGD) / image key / `i.{shopid}.{itemid}` URL |

### Lazada (`lazada_scraper.py`)

| Item | Detail |
| --- | --- |
| Endpoint | `GET https://www.lazada.sg/catalog/?q=…&ajax=true&page=1` (falls back to ZenRows `js_render` if ajax body is not JSON) |
| Proxy | Same ZenRows key; `mode=auto` + `proxy_country=sg` |
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
export APIFY_TOKEN=...           # preferred Shopee path
# export ZENROWS_API_KEY=...     # Lazada + optional Shopee fallback
# export SHOPEE_PROVIDER=auto
# export APIFY_SHOPEE_MAX_ITEMS=100
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

1. **Resolve scrape mode** — skip Amazon/Lazada/ZenRows scrapers when
   `export_only` is true, or when repo variable `ZENROWS_PAUSED` /
   `SCRAPE_PAUSED` is `true` (unless `force_scrape` is set on workflow_dispatch).
   **Exception:** if `APIFY_TOKEN` is set while paused (and not `export_only`),
   Shopee Apify still runs (`run_shopee=true`).
2. Always run Amazon (`scraper.py`) when not skipped — **hard** fail-closed
3. If `APIFY_TOKEN` and/or `ZENROWS_API_KEY` set: run `shopee_scraper.py`
   (Apify preferred); if `ZENROWS_API_KEY` and not paused: run `lazada_scraper.py`
   (`SEA_SOFT_FAIL=1`, `continue-on-error: true`)
4. Optionally run BuyWhere / Shopee Affiliate / Lazada Affiliate when their
   secrets are set (otherwise skip with a notice — parked paths)
5. `export_json.py` → commit `diskprices.db` + `data/products.json` when non-empty
   (always runs, including pause / export_only)

**Secret to add:** GitHub → Settings → Secrets → Actions → `APIFY_TOKEN`
(Apify API token). Optional vars: `SHOPEE_PROVIDER`, `APIFY_SHOPEE_MAX_ITEMS`.

**Bright Data:** still pending zone provisioning (`web_unlocker` not found on
account); not wired. Revisit after a Web Unlocker zone exists.

### Pause ZenRows (repo variable)

Stop cron from calling Amazon/ZenRows without disabling the workflow:

1. GitHub → **Settings** → **Secrets and variables** → **Actions** → **Variables**
2. Create `ZENROWS_PAUSED` = `true` (alias: `SCRAPE_PAUSED`)
3. Scheduled runs (and dispatch without override) skip Amazon/Lazada/ZenRows
4. If `APIFY_TOKEN` secret is set, **Shopee Apify still runs** while paused
   (spend-aware: set `APIFY_SHOPEE_MAX_ITEMS` or remove the secret to fully idle)
5. Unpause: set to `false` or delete the variable
6. Emergency full scrape while paused: dispatch with **`force_scrape`**

### Export-only (no scrape)

When ZenRows / Amazon scrape cannot run (e.g. HTTP 402), re-apply accessory
filters and refresh the live catalog without hitting Amazon or SEA:

1. Prefer the **pause variable** above so every cron tick stays export-only, or
2. GitHub → **Actions** → **Scrape Disk Prices** → **Run workflow**
3. Enable **`export_only`** → Run

That path skips Amazon / Shopee / Lazada / affiliate importers and only runs
`export_json.py` (which calls `init_db()` → `deactivate_non_storage()` → write
`data/products.json`) → empty-gate → commit. Amazon scrape remains hard-fail
whenever a full scrape runs.

## Local refresh

```bash
export ZENROWS_API_KEY=...   # Amazon + Lazada
export APIFY_TOKEN=...       # Shopee (preferred)
python scraper.py
python shopee_scraper.py
python lazada_scraper.py
# parked (optional):
# python buywhere_scraper.py
# python shopee_affiliate_scraper.py
# python lazada_affiliate_scraper.py
python export_json.py
```


## Live spike notes (2026-09-19 SGT)

Dispatched **Scrape Disk Prices** on `feat/zenrows-shopee-lazada` with repo `ZENROWS_API_KEY`:

| Attempt | Result |
| --- | --- |
| `premium_proxy` only on search API | ZenRows **REQS002** (needs js_render and/or premium) on Shopee/Lazada |
| `js_render` + `premium_proxy` on search API | Shopee **RESP001** (could not get content); Lazada **read timeout** 90s |
| `mode=auto` on search API | Shopee still **RESP001** (grand total 0) on master after #9 |
| HTML `/search` + `js_render` + `json_response` | Next fix — capture browser `search_items` XHR instead of fetching the JSON API under Stealth |

Amazon path with the same key continues to return hundreds of products. SEA scrapers abort early on ZenRows **AUTH004**/HTTP 402 (usage exceeded) so remaining queries do not keep burning quota. Soft-fail kept SEA steps from blocking the Amazon export.
