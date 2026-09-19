# DiskPrices Singapore 🇸🇬

Compare HDD and SSD prices across Shopee, Lazada, and Amazon.sg.
Find the best cost/TB deals automatically.

## Features

- **Multi-platform scraping**: Shopee, Lazada, Amazon.sg
- **Cost/TB comparison**: Automatically calculated
- **SSD vs HDD classification**: Smart detection
- **Price history**: Track prices over time
- **Daily updates**: GitHub Actions automated scraping

## Tech Stack

- **Frontend**: Vite + React + Tailwind CSS
- **Backend**: FastAPI + Playwright
- **Database**: SQLite
- **Deployment**: Vercel (frontend) + GitHub Actions (scraping)

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/diskprices` | List all products with filters |
| `GET /api/diskprices/stats` | Get statistics |
| `POST /api/diskprices/scrape` | Trigger manual scrape |

## Filters

- `platform`: Shopee, Lazada, Amazon.sg
- `is_ssd`: true/false
- `sort_by`: cost_per_tb, price, capacity

## Data sources

Sources: **Amazon.sg** + **Shopee.sg** / **Lazada.sg** via ZenRows (`ZENROWS_API_KEY`); BuyWhere and official affiliate APIs are parked. See [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md).

## Setup

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Scraper

```bash
pip install playwright
playwright install chromium
python scraper.py
```

## GitHub Actions

Scheduled scraping commits `diskprices.db` + `data/products.json`.

### Pause ZenRows / scraping (no credit burn)

While ZenRows is paused (e.g. HTTP 402), set a **repository variable** so cron
takes the export-only path automatically:

1. GitHub → **Settings** → **Secrets and variables** → **Actions** → **Variables**
2. **New repository variable**: name `ZENROWS_PAUSED` (or `SCRAPE_PAUSED`), value `true`
3. Cron and default dispatch then skip all scrapers, still run `export_json.py` + commit
4. To unpause: set the variable to `false` or delete it
5. Emergency full scrape while paused: **Run workflow** → enable **`force_scrape`**

Manual one-shot without the variable: **Actions → Scrape Disk Prices → Run workflow → enable `export_only`**.
See [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md#export-only-no-scrape).

## License

MIT
