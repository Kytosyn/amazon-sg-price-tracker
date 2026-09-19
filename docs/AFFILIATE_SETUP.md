# Affiliate API setup (Singapore)

Step-by-step for DiskPrices SG. Credentials go in **GitHub → Settings → Secrets and variables → Actions** (never commit them).

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

If either secret is empty, the **Scrape Disk Prices** workflow **skips** Shopee with a notice. When both are set, it runs `shopee_affiliate_scraper.py` after Amazon.

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

### Important: do not enable Lazada CI secrets yet

`lazada_affiliate_scraper.py` is a **structured stub**. Public docs did not expose a confirmed affiliate **product-search** endpoint without login. Seller REST (`https://api.lazada.sg/rest`, e.g. `/products/get`) is **not** marketplace search.

Once you can see the Affiliate API docs:

1. Note the exact product-search / offer-feed path + signing sample.
2. Hand that to the repo (or paste into the TODO in `lazada_affiliate_scraper.py`).
3. Only then add the GitHub secrets so the workflow step can succeed.

Until then, leave Lazada secrets empty so CI **skips** the step.

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

## 4. What works without credentials

| Component | Without secrets |
| --- | --- |
| Code / PR / docs | Fully reviewable |
| Amazon local scrape | Works from a non-blocked IP |
| Amazon on Actions | Usually 0 results without ZenRows/ScraperAPI |
| Shopee script locally | Exit 1 + signup hint |
| Shopee on Actions | Skipped if secrets empty |
| Lazada script | Exit 1 + apply/TODO (stub) |
| Lazada on Actions | Skipped if secrets empty |

Eddy approval needed for: Shopee affiliate account + App ID/Secret; Lazada affiliate approval + Open API docs/endpoint + App Key/Secret (and token if any).
