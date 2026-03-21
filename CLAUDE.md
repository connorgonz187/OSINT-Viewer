# OSINT Viewer

## Overview

A full-stack OSINT (Open-Source Intelligence) dashboard that visualizes military aircraft tracking and global conflict events on an interactive 3D globe. Combines real-time ADS-B transponder data with NLP-extracted conflict events from RSS news feeds.

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy (async), APScheduler, spaCy NLP, httpx
- **Frontend:** React 18, TypeScript, Vite, react-globe.gl (Three.js), Nginx (prod)
- **Database:** PostgreSQL 16 + PostGIS 3.4
- **AI:** Groq (Llama 3.3 70B, free) with Claude fallback for event classification
- **Containerization:** Docker Compose (3 services: db, backend, frontend)

## Project Structure

```
backend/                    # FastAPI Python backend
  main.py                   # App entry point, lifespan, routers
  config.py                 # Pydantic settings from env vars
  database/
    connection.py            # SQLAlchemy async engine
    models.py                # Event, FlightTrack, Source models
  flight_service/
    opensky.py               # OpenSky Network API client
    military_filter.py       # ICAO ranges, callsign patterns, aircraft type detection
    router.py                # /api/flights/* endpoints
  scraping_service/
    rss_scraper.py           # RSS feed fetching (14+ sources)
    nlp_extractor.py         # spaCy NER + regex event classification (7 types)
    ai_classifier.py         # Groq/Claude LLM batch classification
    router.py                # /api/events/* endpoints
  geolocation_service/
    geocoder.py              # Nominatim geocoding with conflict region overrides
  scheduler/
    jobs.py                  # APScheduler: flights every 60s, scraping every 900s
  agent/
    reviewer.py              # Rule-based + LLM code review agent
frontend/                   # React TypeScript frontend
  src/
    App.tsx                  # Main component: globe, markers, polling
    components/FilterPanel.tsx  # Sidebar: filters, AI classify button, legend
    hooks/useApi.ts          # useFlights (30s poll), useEvents (60s poll)
    types/index.ts           # TypeScript interfaces, event type colors
database/
  init.sql                  # PostGIS schema, default RSS sources
docker-compose.yml          # PostgreSQL, backend, frontend services
```

## Running

```bash
# Docker (production)
docker compose up --build -d
# Frontend: http://watcher:3000  Backend: http://watcher:8000

# Local dev
cd backend && pip install -r requirements.txt && python -m spacy download en_core_web_sm && uvicorn main:app --reload
cd frontend && npm install && npm run dev  # Vite on :5173, proxies /api to :8000
```

## Key API Endpoints

- `GET /api/flights/live` - Live military aircraft positions (cached)
- `GET /api/flights/history?icao24=&hours=24` - Historical flight tracks
- `GET /api/events` - Conflict events (supports time range, type, bbox filters)
- `GET /api/events/types` - Distinct event types in DB
- `POST /api/events/ai-classify` - Trigger AI classification batch
- `GET /api/health` - Health check
- `GET /api/review` - Run code review agent

## Environment Variables

Configured via `.env` file (not committed):
- `POSTGRES_USER/PASSWORD/DB` - Database credentials (defaults: osint/changeme/osint_viewer)
- `DATABASE_URL` - Auto-composed in docker-compose
- `OPENSKY_USERNAME/PASSWORD` - Optional OpenSky API auth
- `ANTHROPIC_API_KEY` - Claude API (optional, for AI classification fallback + code review)
- `GROQ_API_KEY` - Groq API (optional, preferred for AI classification)
- `FLIGHT_REFRESH_INTERVAL` - Seconds between flight updates (default 60)
- `SCRAPING_REFRESH_INTERVAL` - Seconds between scraping runs (default 900)
- `CORS_ORIGINS` - Comma-separated allowed origins (default: `http://localhost:3000,http://localhost:5173`)
- `ENABLE_REVIEW` - Set to `1` to enable the `/api/review` code review endpoint (disabled by default)

## Architecture Notes

- Deployed on Raspberry Pi 5 — performance and memory efficiency are priorities
- Backend is fully async (asyncpg, httpx, APScheduler async jobs)
- PostGIS enables spatial bounding-box queries on events and flight tracks
- Military aircraft detection uses 3 signals: ICAO hex ranges, callsign prefixes, aircraft type codes
- NLP pipeline: spaCy NER extracts locations -> regex classifies 7 event types -> geocoder resolves coordinates
- AI classification is on-demand (user-triggered), not automatic; rate-limited to one concurrent run
- Geocoder has hardcoded overrides for disputed/conflict regions to avoid misresolution
- Geocoder rate-limits Nominatim calls (1 req/s) using smart delta sleep, not unconditional delay
- RSS feeds fetched with a shared httpx client (single connection pool, not per-feed)
- Duplicate event detection uses batch queries instead of per-article DB lookups
- Flight cache refresh and AI classification are guarded by asyncio.Lock to prevent concurrent runs
- Frontend renders a 3D globe with custom airplane/pin SVG markers, color-coded by type
- Frontend HTML tooltips escape all user-supplied content to prevent XSS
- DB port is restricted to localhost in docker-compose (not exposed to network)
