# OSINT Viewer

Web-based intelligence dashboard that visualizes global open-source intelligence (OSINT) on an interactive world map. Displays live military flight tracking via ADS-B and conflict events extracted from news sources via NLP.

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────┐
│   Frontend   │────▶│          FastAPI Backend              │
│  React/TS    │     │                                      │
│  Leaflet Map │     │  ┌──────────┐  ┌─────────────────┐  │
└─────────────┘     │  │ Flight   │  │ Scraping        │  │
                    │  │ Service  │  │ Service + NLP   │  │
                    │  └──────────┘  └─────────────────┘  │
                    │  ┌──────────┐  ┌─────────────────┐  │
                    │  │ Geo      │  │ Code Review     │  │
                    │  │ Service  │  │ Agent           │  │
                    │  └──────────┘  └─────────────────┘  │
                    │  ┌──────────────────────────────┐    │
                    │  │ APScheduler (periodic jobs)  │    │
                    │  └──────────────────────────────┘    │
                    └────────────────┬─────────────────────┘
                                     │
                    ┌────────────────▼─────────────────────┐
                    │   PostgreSQL + PostGIS                │
                    └──────────────────────────────────────┘
```

## Quick Start (Docker)

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env with your settings (all optional — works with defaults)
```

### 2. Launch with Docker Compose

```bash
docker compose up --build -d
```

This starts:
- **PostgreSQL + PostGIS** on port 5432
- **FastAPI backend** on port 8000
- **React frontend** (nginx) on port 3000

### 3. Access the dashboard

Open **http://localhost:3000** in your browser.

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/health` | Health check |
| `GET /api/flights/live` | Live military aircraft positions |
| `GET /api/flights/history?icao24=&hours=24` | Historical flight tracks |
| `GET /api/events?hours=168&event_type=` | Conflict events with filters |
| `GET /api/events/types` | Available event type categories |
| `GET /api/review` | Run code review agent |

## Configuration

Environment variables (`.env`):

| Variable | Description | Default |
|---|---|---|
| `POSTGRES_USER` | DB username | `osint` |
| `POSTGRES_PASSWORD` | DB password | `changeme` |
| `OPENSKY_USERNAME` | OpenSky API credentials (optional) | — |
| `OPENSKY_PASSWORD` | OpenSky API credentials (optional) | — |
| `ANTHROPIC_API_KEY` | Claude API for code review agent | — |
| `FLIGHT_REFRESH_INTERVAL` | Seconds between flight data pulls | `60` |
| `SCRAPING_REFRESH_INTERVAL` | Seconds between scraping runs | `900` |

## Features

- **Military Flight Tracking**: Filters ADS-B data from OpenSky Network using ICAO hex ranges, callsign patterns, and aircraft type codes
- **Conflict Event Detection**: Scrapes RSS feeds (BBC, Al Jazeera, NYT, etc.), runs spaCy NER to extract locations, classifies events (missile strikes, airstrikes, explosions, etc.)
- **Interactive Map**: Dark-themed Leaflet map with toggleable layers, color-coded markers, and popup details
- **Geospatial Queries**: PostGIS-backed bounding box and proximity filtering
- **Time Controls**: Filter events by 24h / 7d / 30d
- **Code Review Agent**: Rule-based + optional LLM-powered security and quality analysis

## Data Sources

All OSINT — no classified or restricted data:
- OpenSky Network (ADS-B transponder data)
- BBC World RSS
- Al Jazeera RSS
- NYT World RSS
- Nominatim/OpenStreetMap (geocoding)

## Development

### Backend (local)

```bash
cd backend
pip install -r requirements.txt
python -m spacy download en_core_web_sm
uvicorn main:app --reload
```

### Frontend (local)

```bash
cd frontend
npm install
npm run dev
```

## Project Structure

```
├── backend/
│   ├── flight_service/      # OpenSky API + military filtering
│   ├── scraping_service/    # RSS scraping + NLP extraction
│   ├── geolocation_service/ # Nominatim geocoding
│   ├── agent/               # Code review agent
│   ├── database/            # SQLAlchemy models + PostGIS
│   ├── scheduler/           # APScheduler periodic jobs
│   ├── config.py
│   └── main.py
├── frontend/
│   └── src/
│       ├── components/      # Map, FilterPanel, FlightLayer, EventLayer
│       ├── hooks/           # API hooks
│       └── types/           # TypeScript interfaces
├── database/
│   └── init.sql             # Schema + PostGIS setup
├── docker-compose.yml
└── .env.example
```
 