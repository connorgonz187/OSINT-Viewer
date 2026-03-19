import { useState, useEffect, useCallback } from "react";
import type {
  FlightsResponse,
  EventsResponse,
  MilitaryFlight,
  ConflictEvent,
} from "../types";

const API_BASE = "/api";

async function fetchJson<T>(url: string): Promise<T> {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export function useFlights(enabled: boolean, refreshMs = 30000) {
  const [flights, setFlights] = useState<MilitaryFlight[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    try {
      const data = await fetchJson<FlightsResponse>(
        `${API_BASE}/flights/live`
      );
      setFlights(data.flights);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch flights");
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    refresh();
    if (!enabled) return;
    const interval = setInterval(refresh, refreshMs);
    return () => clearInterval(interval);
  }, [refresh, enabled, refreshMs]);

  return { flights, loading, error, refresh };
}

export function useEvents(
  enabled: boolean,
  timeRangeHours: number,
  eventType?: string
) {
  const [events, setEvents] = useState<ConflictEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    try {
      let url = `${API_BASE}/events?hours=${timeRangeHours}`;
      if (eventType) url += `&event_type=${eventType}`;
      const data = await fetchJson<EventsResponse>(url);
      setEvents(data.events);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch events");
    } finally {
      setLoading(false);
    }
  }, [enabled, timeRangeHours, eventType]);

  useEffect(() => {
    refresh();
    if (!enabled) return;
    const interval = setInterval(refresh, 60000);
    return () => clearInterval(interval);
  }, [refresh, enabled]);

  return { events, loading, error, refresh };
}
