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

Daily scraping runs at 9 AM SGT. Results committed to the repository.

## License

MIT
