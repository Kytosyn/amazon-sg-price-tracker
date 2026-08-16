# Amazon.sg Price Tracker

Track prices, view price history, and get alerts for deals on Amazon Singapore.

## Features

- Scrape Amazon.sg product pages for current prices
- Price history tracking with charts
- Category browsing and filtering
- Deal finder (price drops, discounts)
- Price alerts via Discord webhook
- Daily cron-based price updates

## Tech Stack

- **Frontend**: Vite + React + Tailwind CSS + Recharts
- **Backend**: FastAPI + Playwright + SQLite
- **Deployment**: Vercel (frontend) + Railway/Railway (backend)

## Project Structure

```
amazon-sg-price-tracker/
├── frontend/          # Vite + React app
├── backend/           # FastAPI + Playwright scraper
├── database/          # SQLite schema
└── README.md
```

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Environment Variables

```
# Backend
DATABASE_URL=sqlite:///./prices.db
DISCORD_WEBHOOK_URL=your_webhook_url
AMAZON_SG_BASE_URL=https://www.amazon.sg

# Frontend
VITE_API_URL=http://localhost:8000
```
