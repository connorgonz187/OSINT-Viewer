CREATE EXTENSION IF NOT EXISTS postgis;

-- Events table for conflict/incident data
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    location_name VARCHAR(255),
    coordinates GEOMETRY(Point, 4326),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    event_time TIMESTAMPTZ,
    source_url TEXT,
    source_name VARCHAR(100),
    raw_text TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(title, source_url, event_time)
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(event_time);
CREATE INDEX IF NOT EXISTS idx_events_geo ON events USING GIST(coordinates);

-- Flight cache (optional, for historical tracking)
CREATE TABLE IF NOT EXISTS flight_tracks (
    id SERIAL PRIMARY KEY,
    icao24 VARCHAR(10) NOT NULL,
    callsign VARCHAR(20),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    altitude DOUBLE PRECISION,
    velocity DOUBLE PRECISION,
    heading DOUBLE PRECISION,
    on_ground BOOLEAN DEFAULT FALSE,
    coordinates GEOMETRY(Point, 4326),
    seen_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flights_icao ON flight_tracks(icao24);
CREATE INDEX IF NOT EXISTS idx_flights_time ON flight_tracks(seen_at);
CREATE INDEX IF NOT EXISTS idx_flights_geo ON flight_tracks USING GIST(coordinates);

-- Sources registry
CREATE TABLE IF NOT EXISTS sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    url TEXT NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    last_fetched TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed default RSS sources
INSERT INTO sources (name, url, source_type) VALUES
    ('BBC World', 'https://feeds.bbci.co.uk/news/world/rss.xml', 'rss'),
    ('Reuters World', 'https://www.reutersagency.com/feed/?taxonomy=best-sectors&post_type=best', 'rss'),
    ('Al Jazeera', 'https://www.aljazeera.com/xml/rss/all.xml', 'rss'),
    ('ACLED Conflict Data', 'https://acleddata.com/acleddatanew/wp-content/uploads/dlm_uploads/', 'api'),
    ('Liveuamap', 'https://liveuamap.com', 'scrape')
ON CONFLICT (name) DO NOTHING;
