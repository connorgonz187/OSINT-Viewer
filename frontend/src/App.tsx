import { useState, useMemo, useRef, useCallback, useEffect } from "react";
import Globe from "react-globe.gl";
import { useFlights, useEvents } from "./hooks/useApi";
import FilterPanel from "./components/FilterPanel";
import type { Filters, MilitaryFlight, ConflictEvent } from "./types";
import { EVENT_LABELS, EVENT_COLORS } from "./types";

const ALL_EVENT_TYPES = new Set(Object.keys(EVENT_LABELS));

interface GlobePoint {
  lat: number;
  lng: number;
  color: string;
  size: number;
  label: string;
  type: "flight" | "event";
  data: MilitaryFlight | ConflictEvent;
}

function formatAlt(meters: number | null): string {
  if (meters == null) return "N/A";
  return `${Math.round(meters * 3.281)} ft`;
}

function formatSpeed(ms: number | null): string {
  if (ms == null) return "N/A";
  return `${Math.round(ms * 1.944)} kts`;
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function flightTooltip(f: MilitaryFlight): string {
  return `
    <div style="background:#1a2332;color:#e2e8f0;padding:10px 14px;border-radius:8px;font-size:13px;min-width:180px;border:1px solid #2a3a4e;">
      <div style="font-weight:700;font-size:14px;margin-bottom:6px;color:#00ff88;">${f.callsign || f.icao24}</div>
      <div style="display:flex;justify-content:space-between;padding:2px 0;"><span style="color:#94a3b8;">ICAO:</span><span>${f.icao24}</span></div>
      <div style="display:flex;justify-content:space-between;padding:2px 0;"><span style="color:#94a3b8;">Country:</span><span>${f.origin_country}</span></div>
      <div style="display:flex;justify-content:space-between;padding:2px 0;"><span style="color:#94a3b8;">Altitude:</span><span>${formatAlt(f.altitude)}</span></div>
      <div style="display:flex;justify-content:space-between;padding:2px 0;"><span style="color:#94a3b8;">Speed:</span><span>${formatSpeed(f.velocity)}</span></div>
      <div style="display:flex;justify-content:space-between;padding:2px 0;"><span style="color:#94a3b8;">Heading:</span><span>${f.heading != null ? Math.round(f.heading) + "°" : "N/A"}</span></div>
      <div style="display:flex;justify-content:space-between;padding:2px 0;"><span style="color:#94a3b8;">Status:</span><span>${f.on_ground ? "On Ground" : "Airborne"}</span></div>
    </div>
  `;
}

function eventTooltip(e: ConflictEvent): string {
  const color = EVENT_COLORS[e.event_type] || "#ff6600";
  const label = EVENT_LABELS[e.event_type] || e.event_type;
  const summary = e.summary ? e.summary.substring(0, 200) + (e.summary.length > 200 ? "..." : "") : "";
  return `
    <div style="background:#1a2332;color:#e2e8f0;padding:10px 14px;border-radius:8px;font-size:13px;max-width:320px;border:1px solid #2a3a4e;">
      <span style="background:${color};color:white;padding:2px 8px;border-radius:3px;font-size:11px;font-weight:600;">${label}</span>
      <div style="font-weight:700;font-size:14px;margin:6px 0 4px;">${e.title}</div>
      ${summary ? `<div style="color:#94a3b8;line-height:1.4;margin-bottom:4px;">${summary}</div>` : ""}
      <div style="color:#94a3b8;padding:2px 0;">Location: ${e.location_name || "Unknown"}</div>
      <div style="color:#94a3b8;padding:2px 0;">Time: ${formatTime(e.event_time)}</div>
      <div style="color:#94a3b8;padding:2px 0;">Source: ${e.source_name}</div>
      ${e.source_url ? `<a href="${e.source_url}" target="_blank" rel="noopener noreferrer" style="color:#3b82f6;font-size:12px;">View Source Article</a>` : ""}
    </div>
  `;
}

export default function App() {
  const globeRef = useRef<any>(null);
  const [filters, setFilters] = useState<Filters>({
    showFlights: true,
    showEvents: true,
    eventTypes: new Set(ALL_EVENT_TYPES),
    timeRangeHours: 168,
  });

  const {
    flights,
    loading: flightsLoading,
  } = useFlights(filters.showFlights);

  const {
    events,
    loading: eventsLoading,
  } = useEvents(filters.showEvents, filters.timeRangeHours);

  const filteredEvents = useMemo(
    () => events.filter((e) => filters.eventTypes.has(e.event_type)),
    [events, filters.eventTypes]
  );

  const loading = flightsLoading || eventsLoading;

  // Build globe points
  const points: GlobePoint[] = useMemo(() => {
    const pts: GlobePoint[] = [];

    if (filters.showFlights) {
      for (const f of flights) {
        pts.push({
          lat: f.latitude,
          lng: f.longitude,
          color: f.on_ground ? "#888888" : "#00ff88",
          size: 0.3,
          label: flightTooltip(f),
          type: "flight",
          data: f,
        });
      }
    }

    if (filters.showEvents) {
      for (const e of filteredEvents) {
        pts.push({
          lat: e.latitude,
          lng: e.longitude,
          color: EVENT_COLORS[e.event_type] || "#ff6600",
          size: 0.5,
          label: eventTooltip(e),
          type: "event",
          data: e,
        });
      }
    }

    return pts;
  }, [flights, filteredEvents, filters.showFlights, filters.showEvents]);

  // Set initial globe position and controls
  useEffect(() => {
    if (globeRef.current) {
      const controls = globeRef.current.controls();
      if (controls) {
        controls.autoRotate = false;
        controls.enableDamping = true;
        controls.dampingFactor = 0.1;
      }
      // Start looking at Middle East / conflict area
      globeRef.current.pointOfView({ lat: 30, lng: 35, altitude: 2.5 }, 1000);
    }
  }, []);

  const handlePointClick = useCallback((point: any) => {
    if (point.type === "event") {
      const e = point.data as ConflictEvent;
      if (e.source_url) {
        window.open(e.source_url, "_blank");
      }
    }
  }, []);

  return (
    <>
      <header className="header">
        <h1>OSINT VIEWER</h1>
        <div className="stats">
          <span>
            <span className="dot green" />
            {flights.length} Military Aircraft
          </span>
          <span>
            <span className="dot red" />
            {filteredEvents.length} Events
          </span>
        </div>
      </header>
      <div className="main-layout">
        <FilterPanel filters={filters} onChange={setFilters} />
        <div className="globe-container">
          {loading && <div className="loading-indicator">Updating...</div>}
          <Globe
            ref={globeRef}
            globeImageUrl="//unpkg.com/three-globe/example/img/earth-blue-marble.jpg"
            bumpImageUrl="//unpkg.com/three-globe/example/img/earth-topology.png"
            backgroundImageUrl="//unpkg.com/three-globe/example/img/night-sky.png"
            pointsData={points}
            pointLat="lat"
            pointLng="lng"
            pointColor="color"
            pointRadius="size"
            pointAltitude={0.01}
            pointLabel="label"
            onPointClick={handlePointClick}
            pointsMerge={false}
            atmosphereColor="#3a86ff"
            atmosphereAltitude={0.2}
            animateIn={true}
            width={undefined}
            height={undefined}
          />
        </div>
      </div>
    </>
  );
}
