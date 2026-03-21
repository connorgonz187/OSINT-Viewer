import { useState, useMemo, useRef, useCallback, useEffect } from "react";
import Globe from "react-globe.gl";

function useContainerSize(ref: React.RefObject<HTMLDivElement | null>) {
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({ width, height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return size;
}
import { useFlights, useEvents } from "./hooks/useApi";
import FilterPanel from "./components/FilterPanel";
import type { Filters, MilitaryFlight, ConflictEvent } from "./types";
import { EVENT_LABELS, EVENT_COLORS } from "./types";

const ALL_EVENT_TYPES = new Set(Object.keys(EVENT_LABELS));

interface GlobePoint {
  lat: number;
  lng: number;
  size: number;
  color: string;
  altitude: number;
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

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function safeUrl(url: string): string | null {
  try {
    const parsed = new URL(url);
    return (parsed.protocol === "http:" || parsed.protocol === "https:") ? parsed.href : null;
  } catch {
    return null;
  }
}

function flightTooltip(f: MilitaryFlight): string {
  return `
    <div style="background:#1a2332;color:#e2e8f0;padding:10px 14px;border-radius:8px;font-size:13px;min-width:180px;border:1px solid #2a3a4e;">
      <div style="font-weight:700;font-size:14px;margin-bottom:6px;color:#00ff88;">${escapeHtml(f.callsign || f.icao24)}</div>
      <div style="display:flex;justify-content:space-between;padding:2px 0;"><span style="color:#94a3b8;">ICAO:</span><span>${escapeHtml(f.icao24)}</span></div>
      <div style="display:flex;justify-content:space-between;padding:2px 0;"><span style="color:#94a3b8;">Country:</span><span>${escapeHtml(f.origin_country)}</span></div>
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
  return `
    <div style="background:#1a2332;color:#e2e8f0;padding:10px 14px;border-radius:8px;font-size:13px;max-width:280px;border:1px solid #2a3a4e;">
      <span style="background:${color};color:white;padding:2px 8px;border-radius:3px;font-size:11px;font-weight:600;">${escapeHtml(label)}</span>
      <div style="font-weight:700;font-size:13px;margin:6px 0 4px;">${escapeHtml(e.title)}</div>
      <div style="color:#94a3b8;padding:2px 0;">Location: ${escapeHtml(e.location_name || "Unknown")}</div>
      <div style="color:#94a3b8;font-size:11px;">Click for details</div>
    </div>
  `;
}

export default function App() {
  const globeRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { width, height } = useContainerSize(containerRef);
  const [filters, setFilters] = useState<Filters>({
    showFlights: true,
    showEvents: true,
    eventTypes: new Set(ALL_EVENT_TYPES),
    timeRangeHours: 168,
  });
  const [selected, setSelected] = useState<GlobePoint | null>(null);

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

  // Build 3D point markers
  const points: GlobePoint[] = useMemo(() => {
    const items: GlobePoint[] = [];

    if (filters.showFlights) {
      for (const f of flights) {
        items.push({
          lat: f.latitude,
          lng: f.longitude,
          size: 0.35,
          color: f.on_ground ? "#888888" : "#00ff88",
          altitude: 0.01,
          type: "flight",
          data: f,
        });
      }
    }

    if (filters.showEvents) {
      for (const e of filteredEvents) {
        items.push({
          lat: e.latitude,
          lng: e.longitude,
          size: 0.3,
          color: EVENT_COLORS[e.event_type] || "#ff6600",
          altitude: 0.04,
          type: "event",
          data: e,
        });
      }
    }

    return items;
  }, [flights, filteredEvents, filters.showFlights, filters.showEvents]);

  // Ring pulse effect for most recent events only (cap at 25 for Pi performance)
  const rings = useMemo(() => {
    if (!filters.showEvents) return [];
    const sorted = [...filteredEvents].sort(
      (a, b) => new Date(b.event_time).getTime() - new Date(a.event_time).getTime()
    );
    return sorted.slice(0, 25).map((e) => ({
      lat: e.latitude,
      lng: e.longitude,
      maxR: 1.5,
      propagationSpeed: 1.5,
      repeatPeriod: 2000,
      color: EVENT_COLORS[e.event_type] || "#ff6600",
    }));
  }, [filteredEvents, filters.showEvents]);

  const getPointLabel = useCallback((d: object) => {
    const p = d as GlobePoint;
    return p.type === "flight"
      ? flightTooltip(p.data as MilitaryFlight)
      : eventTooltip(p.data as ConflictEvent);
  }, []);

  const handlePointClick = useCallback((d: object) => {
    setSelected(d as GlobePoint);
  }, []);

  // Set initial globe position and controls
  useEffect(() => {
    if (globeRef.current) {
      const controls = globeRef.current.controls();
      if (controls) {
        controls.autoRotate = false;
        controls.enableDamping = true;
        controls.dampingFactor = 0.1;
      }
      globeRef.current.pointOfView({ lat: 30, lng: 35, altitude: 2.5 }, 1000);
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
        <div className="globe-container" ref={containerRef}>
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
            pointAltitude="altitude"
            pointRadius="size"
            pointLabel={getPointLabel}
            onPointClick={handlePointClick}
            ringsData={rings}
            ringLat="lat"
            ringLng="lng"
            ringColor="color"
            ringMaxRadius="maxR"
            ringPropagationSpeed="propagationSpeed"
            ringRepeatPeriod="repeatPeriod"
            atmosphereColor="#3a86ff"
            atmosphereAltitude={0.2}
            animateIn={true}
            width={width || undefined}
            height={height || undefined}
          />
          {selected && (
            <DetailPanel marker={selected} onClose={() => setSelected(null)} />
          )}
        </div>
      </div>
    </>
  );
}

function DetailPanel({ marker, onClose }: { marker: GlobePoint; onClose: () => void }) {
  if (marker.type === "flight") {
    const f = marker.data as MilitaryFlight;
    return (
      <div className="detail-panel">
        <button className="detail-close" onClick={onClose}>&times;</button>
        <div className="detail-header flight">{f.callsign || f.icao24}</div>
        <div className="detail-row"><span>ICAO</span><span>{f.icao24}</span></div>
        <div className="detail-row"><span>Country</span><span>{f.origin_country}</span></div>
        <div className="detail-row"><span>Altitude</span><span>{formatAlt(f.altitude)}</span></div>
        <div className="detail-row"><span>Speed</span><span>{formatSpeed(f.velocity)}</span></div>
        <div className="detail-row"><span>Heading</span><span>{f.heading != null ? Math.round(f.heading) + "\u00B0" : "N/A"}</span></div>
        <div className="detail-row"><span>Status</span><span>{f.on_ground ? "On Ground" : "Airborne"}</span></div>
      </div>
    );
  }

  const e = marker.data as ConflictEvent;
  const color = EVENT_COLORS[e.event_type] || "#ff6600";
  const label = EVENT_LABELS[e.event_type] || e.event_type;
  const href = e.source_url ? safeUrl(e.source_url) : null;

  return (
    <div className="detail-panel">
      <button className="detail-close" onClick={onClose}>&times;</button>
      <span className="detail-badge" style={{ background: color }}>{label}</span>
      <div className="detail-header">{e.title}</div>
      {e.summary && (
        <p className="detail-summary">
          {e.summary.substring(0, 400)}{e.summary.length > 400 ? "..." : ""}
        </p>
      )}
      <div className="detail-row"><span>Location</span><span>{e.location_name || "Unknown"}</span></div>
      <div className="detail-row"><span>Time</span><span>{formatTime(e.event_time)}</span></div>
      <div className="detail-row"><span>Source</span><span>{e.source_name}</span></div>
      {href && (
        <a href={href} target="_blank" rel="noopener noreferrer" className="detail-link">
          View Source Article
        </a>
      )}
    </div>
  );
}
