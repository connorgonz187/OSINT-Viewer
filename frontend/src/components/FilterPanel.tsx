import { useState } from "react";
import type { Filters } from "../types";
import { EVENT_LABELS, EVENT_COLORS } from "../types";

interface Props {
  filters: Filters;
  onChange: (f: Filters) => void;
}

interface AiResult {
  status: string;
  new_events?: number;
  reclassified?: number;
  total_articles?: number;
  ai_classified?: number;
  ai_skipped?: number;
}

const TIME_OPTIONS = [
  { hours: 24, label: "24h" },
  { hours: 168, label: "7d" },
  { hours: 720, label: "30d" },
];

export default function FilterPanel({ filters, onChange }: Props) {
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResult, setAiResult] = useState<AiResult | null>(null);

  const toggleEventType = (type: string) => {
    const next = new Set(filters.eventTypes);
    if (next.has(type)) next.delete(type);
    else next.add(type);
    onChange({ ...filters, eventTypes: next });
  };

  const timeLabel =
    filters.timeRangeHours <= 24
      ? "24 hours"
      : filters.timeRangeHours <= 168
        ? "7 days"
        : "30 days";

  const runAiClassification = async () => {
    setAiLoading(true);
    setAiResult(null);
    try {
      const resp = await fetch("/api/events/ai-classify", { method: "POST" });
      if (!resp.ok) throw new Error(`API error: ${resp.status}`);
      const data: AiResult = await resp.json();
      setAiResult(data);
    } catch (e) {
      setAiResult({ status: "error", error_msg: e instanceof Error ? e.message : "Unknown error" } as any);
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <aside className="sidebar">
      {/* Layer toggles */}
      <section>
        <h3>Layers</h3>
        <div className="toggle-row">
          <label>
            <input
              type="checkbox"
              checked={filters.showFlights}
              onChange={() =>
                onChange({ ...filters, showFlights: !filters.showFlights })
              }
            />
            Military Flights
          </label>
        </div>
        <div className="toggle-row">
          <label>
            <input
              type="checkbox"
              checked={filters.showEvents}
              onChange={() =>
                onChange({ ...filters, showEvents: !filters.showEvents })
              }
            />
            Conflict Events
          </label>
        </div>
      </section>

      {/* AI Classification */}
      <section>
        <h3>AI Classification</h3>
        <button
          className="ai-button"
          onClick={runAiClassification}
          disabled={aiLoading}
        >
          {aiLoading ? "Classifying..." : "Reclassify with AI"}
        </button>
        <p className="ai-hint">
          Uses Groq AI to accurately classify and geolocate events
        </p>
        {aiResult && (
          <div className={`ai-result ${aiResult.status === "error" ? "error" : ""}`}>
            {aiResult.status === "ok" ? (
              <>
                <span>{aiResult.new_events} new</span>
                <span>{aiResult.reclassified} reclassified</span>
                <span>{aiResult.ai_classified} classified / {aiResult.ai_skipped} skipped</span>
              </>
            ) : aiResult.status === "ai_unavailable" ? (
              <span>No API key configured</span>
            ) : (
              <span>Classification failed{(aiResult as any).error_msg ? `: ${(aiResult as any).error_msg}` : ""}</span>
            )}
          </div>
        )}
      </section>

      {/* Time range */}
      <section>
        <h3>Time Range</h3>
        <div className="time-slider">
          <div className="current">{timeLabel}</div>
          <input
            type="range"
            min={0}
            max={2}
            step={1}
            value={TIME_OPTIONS.findIndex(
              (o) => o.hours === filters.timeRangeHours
            )}
            onChange={(e) =>
              onChange({
                ...filters,
                timeRangeHours: TIME_OPTIONS[Number(e.target.value)].hours,
              })
            }
          />
          <div className="labels">
            {TIME_OPTIONS.map((o) => (
              <span key={o.hours}>{o.label}</span>
            ))}
          </div>
        </div>
      </section>

      {/* Event type filters */}
      <section>
        <h3>Event Types</h3>
        <div className="event-type-filter">
          {Object.entries(EVENT_LABELS).map(([type, label]) => (
            <label key={type} className="event-type-item">
              <input
                type="checkbox"
                checked={filters.eventTypes.has(type)}
                onChange={() => toggleEventType(type)}
              />
              <span
                className="color-dot"
                style={{ background: EVENT_COLORS[type] }}
              />
              {label}
            </label>
          ))}
        </div>
      </section>

      {/* Legend */}
      <section>
        <h3>Legend</h3>
        <div className="legend">
          <div className="legend-item">
            <span
              className="swatch"
              style={{ background: "#00ff88", borderRadius: "50%" }}
            />
            Military Aircraft
          </div>
          {Object.entries(EVENT_LABELS).map(([type, label]) => (
            <div key={type} className="legend-item">
              <span
                className="swatch"
                style={{ background: EVENT_COLORS[type] }}
              />
              {label}
            </div>
          ))}
        </div>
      </section>
    </aside>
  );
}
