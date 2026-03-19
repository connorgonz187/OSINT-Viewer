import { CircleMarker, Popup } from "react-leaflet";
import type { ConflictEvent } from "../types";
import { EVENT_COLORS, EVENT_LABELS } from "../types";

interface Props {
  events: ConflictEvent[];
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function EventLayer({ events }: Props) {
  return (
    <>
      {events.map((e) => {
        const color = EVENT_COLORS[e.event_type] || "#ff6600";
        return (
          <CircleMarker
            key={e.id}
            center={[e.latitude, e.longitude]}
            radius={7}
            pathOptions={{
              color,
              fillColor: color,
              fillOpacity: 0.7,
              weight: 2,
            }}
          >
            <Popup maxWidth={320}>
              <div className="event-popup">
                <span
                  className="event-type-badge"
                  style={{ background: color }}
                >
                  {EVENT_LABELS[e.event_type] || e.event_type}
                </span>
                <h4>{e.title}</h4>
                <p>{e.summary}</p>
                <p>
                  <strong>Location:</strong> {e.location_name}
                </p>
                <p>
                  <strong>Time:</strong> {formatTime(e.event_time)}
                </p>
                <p>
                  <strong>Source:</strong> {e.source_name}
                </p>
                {e.source_url && (
                  <a
                    href={e.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    View Source Article
                  </a>
                )}
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </>
  );
}
