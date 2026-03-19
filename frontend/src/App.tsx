import { useState, useMemo } from "react";
import { MapContainer, TileLayer } from "react-leaflet";
import { useFlights, useEvents } from "./hooks/useApi";
import FilterPanel from "./components/FilterPanel";
import FlightLayer from "./components/FlightLayer";
import EventLayer from "./components/EventLayer";
import type { Filters } from "./types";
import { EVENT_LABELS, EVENT_COLORS } from "./types";

const ALL_EVENT_TYPES = new Set(Object.keys(EVENT_LABELS));

export default function App() {
  const [filters, setFilters] = useState<Filters>({
    showFlights: true,
    showEvents: true,
    eventTypes: new Set(ALL_EVENT_TYPES),
    timeRangeHours: 168, // 7 days
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
        <div className="map-container">
          {loading && <div className="loading-indicator">Updating...</div>}
          <MapContainer
            center={[30, 20]}
            zoom={3}
            style={{ height: "100%", width: "100%" }}
            zoomControl={true}
            preferCanvas={true}
          >
            <TileLayer
              attribution='Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            />
            <TileLayer
              attribution=""
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
              opacity={0.8}
            />
            {filters.showFlights && <FlightLayer flights={flights} />}
            {filters.showEvents && (
              <EventLayer events={filteredEvents} />
            )}
          </MapContainer>
        </div>
      </div>
    </>
  );
}
