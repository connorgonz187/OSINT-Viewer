import { CircleMarker, Popup, Polyline } from "react-leaflet";
import type { MilitaryFlight } from "../types";

interface Props {
  flights: MilitaryFlight[];
}

function formatAlt(meters: number | null): string {
  if (meters == null) return "N/A";
  return `${Math.round(meters * 3.281)} ft`;
}

function formatSpeed(ms: number | null): string {
  if (ms == null) return "N/A";
  return `${Math.round(ms * 1.944)} kts`;
}

export default function FlightLayer({ flights }: Props) {
  return (
    <>
      {flights.map((f) => (
        <CircleMarker
          key={f.icao24}
          center={[f.latitude, f.longitude]}
          radius={5}
          pathOptions={{
            color: "#00ff88",
            fillColor: f.on_ground ? "#888888" : "#00ff88",
            fillOpacity: 0.9,
            weight: 1,
          }}
        >
          <Popup>
            <div className="flight-popup">
              <h4>{f.callsign || f.icao24}</h4>
              <div className="row">
                <span className="label">ICAO:</span>
                <span>{f.icao24}</span>
              </div>
              <div className="row">
                <span className="label">Country:</span>
                <span>{f.origin_country}</span>
              </div>
              <div className="row">
                <span className="label">Altitude:</span>
                <span>{formatAlt(f.altitude)}</span>
              </div>
              <div className="row">
                <span className="label">Speed:</span>
                <span>{formatSpeed(f.velocity)}</span>
              </div>
              <div className="row">
                <span className="label">Heading:</span>
                <span>
                  {f.heading != null ? `${Math.round(f.heading)}°` : "N/A"}
                </span>
              </div>
              <div className="row">
                <span className="label">Status:</span>
                <span>{f.on_ground ? "On Ground" : "Airborne"}</span>
              </div>
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </>
  );
}
