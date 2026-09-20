# Outbound affiliate linking (cost coverage)

DiskPrices SG earns when visitors click through to merchants. This is separate
from the parked Shopee/Lazada *ingest* affiliate APIs in `AFFILIATE_SETUP.md`.

## Amazon.sg Associates

1. Join [Amazon.sg Associates](https://affiliate-program.amazon.sg/).
2. Add site `https://disk.kytosyn.com` during enrollment.
3. Copy your tracking ID (e.g. `yourstore-22`).
4. Set `VITE_AMAZON_ASSOCIATE_TAG` in Vercel (Production) and rebuild.
5. Product cards append `?tag=…` on Amazon.sg links and show the required
   Associates disclosure when the env var is set.

Frontend helper: `frontend/src/lib/affiliate.js`.

## Shopee / Lazada

Outbound click links for SEA platforms are not wired yet. Ingest scrapers remain
the ZenRows path; official affiliate Open APIs stay parked.
