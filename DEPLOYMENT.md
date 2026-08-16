# Deployment configuration for Vercel

## Frontend (Vercel)

1. Connect GitHub repo to Vercel
2. Set root directory to `frontend/`
3. Framework: Vite
4. Build command: `npm run build`
5. Output directory: `dist`

## Backend (Railway/Render)

### Option A: Railway (recommended)
1. Create new project from GitHub repo
2. Set root directory to `backend/`
3. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Environment variables:
   - `DATABASE_URL=sqlite:///./prices.db`
   - `DISCORD_WEBHOOK_URL=your_webhook`

### Option B: Render
1. Create Web Service
2. Root directory: `backend/`
3. Build command: `pip install -r requirements.txt && playwright install chromium`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Price Update Strategy

Since free tiers have limitations:
- Use GitHub Actions for daily scraping (free 2000 minutes/month)
- Store data in SQLite (or upgrade to PostgreSQL on Railway)
- Frontend fetches from backend API

### GitHub Actions Cron

```yaml
# .github/workflows/scrape.yml
name: Daily Price Scrape
on:
  schedule:
    - cron: '0 9 * * *'  # 9 AM SGT daily
  workflow_dispatch:

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r backend/requirements.txt
      - run: playwright install chromium
      - run: python backend/scrape_all.py
        env:
          DATABASE_URL: sqlite:///./prices.db
```

## Cost Breakdown

| Service | Tier | Cost/month |
|---------|------|------------|
| Vercel (frontend) | Hobby | Free |
| Railway (backend) | Starter | $5 |
| SQLite | Built-in | Free |
| GitHub Actions | Free tier | Free |
| **Total** | | **$5** |
