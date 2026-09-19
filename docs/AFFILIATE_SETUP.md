# Affiliate + BuyWhere setup (Singapore)

Step-by-step for DiskPrices SG. Credentials go in **GitHub → Settings → Secrets and variables → Actions** (never commit them).

Also see **[DATA_SOURCES.md](./DATA_SOURCES.md)** for the full source matrix (Amazon + BuyWhere + affiliates).

---

## 0. BuyWhere (optional multi-platform)

One key covers Shopee / Lazada / Amazon.sg / other SG merchants via `buywhere_scraper.py`.

1. Get a key from **[https://buywhere.ai/quickstart](https://buywhere.ai/quickstart)**
2. Add GitHub secret `BUYWHERE_API_KEY`
3. Workflow runs BuyWhere after Amazon when the secret is set; skips with a notice when empty

```bash
export BUYWHERE_API_KEY=bw_live_...
python buywhere_scraper.py
```

---

## 1. Shopee Affiliate (SG) — implemented

### Sign up

1. Open **[https://affiliate.shopee.sg/](https://affiliate.shopee.sg/)** and register / log in with your Shopee account.
2. Complete affiliate onboarding (profile, payment details, any media/site review Shopee asks for).
3. Wait for **approval** if the account is pending (Open API access may be gated until approved).

### App ID + Secret

1. In the SG Affiliate portal, open **Open API** / developer credentials (wording varies; look for App ID / Secret or Credential).
2. Create an application if prompted and copy:
   - **App ID** → GitHub secret `SHOPEE_AFFILIATE_APP_ID`
   - **Secret** → GitHub secret `SHOPEE_AFFILIATE_SECRET`
3. Confirm the GraphQL base used by this repo:
   - `https://open-api.affiliate.shopee.com.sg/graphql`

### GitHub secrets

| Secret name | Value |
| --- | --- |
| `SHOPEE_AFFILIATE_APP_ID` | App ID from portal |
| `SHOPEE_AFFILIATE_SECRET` | App Secret from portal |

### Verify locally

```bash
export SHOPEE_AFFILIATE_APP_ID=...
export SHOPEE_AFFILIATE_SECRET=...
python shopee_affiliate_scraper.py
```

Auth format used by the script:

`Authorization: SHA256 Credential={appId},Timestamp={unix},Signature={sha256(appId+timestamp+body+secret)}`

Fail-closed: missing secrets or **0** storage products → exit code 1.

### Workflow

If either secret is empty, the **Scrape Disk Prices** workflow **skips** Shopee with a notice. When both are set, it runs `shopee_affiliate_scraper.py` after Amazon (and after BuyWhere if enabled).

---

## 2. Lazada Affiliate (SG) — stub until docs access

### Sign up

1. Open **[https://www.lazada.sg/lazada-affiliate-program](https://www.lazada.sg/lazada-affiliate-program)** and submit the affiliate application.
2. Complete media / site review as required by Lazada.
3. Wait for **approval** (account + any Open API entitlement).

### Open Platform credentials

1. After approval, sign in to **[https://open.lazada.com/](https://open.lazada.com/)** (and/or the Lazada Affiliate portal linked from your approval email).
2. Create or open an **Affiliate**-capable app (not a seller-only OMS app unless Lazada says otherwise).
3. Copy:
   - **App Key** → `LAZADA_AFFILIATE_APP_KEY`
   - **App Secret** → `LAZADA_AFFILIATE_APP_SECRET`
   - **Access Token** (if the console issues OAuth tokens) → `LAZADA_AFFILIATE_ACCESS_TOKEN`

### GitHub secrets

| Secret name | Value |
| --- | --- |
| `LAZADA_AFFILIATE_APP_KEY` | App Key |
| `LAZADA_AFFILIATE_APP_SECRET` | App Secret |
| `LAZADA_AFFILIATE_ACCESS_TOKEN` | Access token if required (optional until confirmed) |

### Stub behaviour (CI-safe)

`lazada_affiliate_scraper.py` is a **structured stub**. While `ENDPOINT` is unset:

- Workflow skips entirely if Lazada secrets are empty
- If secrets are present but the stub is still unwired, the script **exits 0 with a notice** so CI does not fail

Once you can see the Affiliate API docs:

1. Note the exact product-search / offer-feed path + signing sample.
2. Hand that to the repo (or paste into the TODO in `lazada_affiliate_scraper.py`).
3. Only then expect a real fail-closed product import.

### Signing (from public LazOP docs — verify against Affiliate docs)

Typical LazOP request params: `app_key`, `timestamp` (ms), `sign_method=sha256`, `access_token` (when needed), API-specific fields.

`sign` = HMAC-SHA256 over `api_path` + concatenated sorted `key+value` pairs, keyed with `app_secret`.

Reference (may require login): [open.lazada.com signing doc](https://open.lazada.com/apps/doc/doc?nodeId=10450&docId=108068).

---

## 3. Amazon (unchanged)

| Secret | Purpose |
| --- | --- |
| `ZENROWS_API_KEY` or `SCRAPERAPI_KEY` | Unblock Amazon.sg HTML scrape on GitHub Actions |

---

## 4. Secret checklist

| Secret | Enables |
| --- | --- |
| `ZENROWS_API_KEY` / `SCRAPERAPI_KEY` | Amazon.sg on Actions |
| `BUYWHERE_API_KEY` | BuyWhere multi-platform import |
| `SHOPEE_AFFILIATE_APP_ID` + `SHOPEE_AFFILIATE_SECRET` | Official Shopee Affiliate |
| `LAZADA_AFFILIATE_APP_KEY` + `LAZADA_AFFILIATE_APP_SECRET` (+ optional token) | Lazada Affiliate (stub until endpoint) |

## 5. What works without credentials

| Component | Without secrets |
| --- | --- |
| Code / PR / docs | Fully reviewable |
| Amazon local scrape | Works from a non-blocked IP |
| Amazon on Actions | Usually 0 results without ZenRows/ScraperAPI |
| BuyWhere on Actions | Skipped if secret empty |
| Shopee script locally | Exit 1 + signup hint |
| Shopee on Actions | Skipped if secrets empty |
| Lazada script (stub) | Exit 0 + notice while `ENDPOINT` unset |
| Lazada on Actions | Skipped if secrets empty |

Eddy approval needed for: BuyWhere key; Shopee affiliate App ID/Secret; Lazada affiliate approval + Open API docs/endpoint + App Key/Secret (and token if any).
