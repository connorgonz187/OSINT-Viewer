export interface MilitaryFlight {
  icao24: string;
  callsign: string | null;
  origin_country: string;
  latitude: number;
  longitude: number;
  altitude: number | null;
  velocity: number | null;
  heading: number | null;
  on_ground: boolean;
  last_contact: string;
}

export interface ConflictEvent {
  id: number;
  event_type: string;
  title: string;
  summary: string;
  location_name: string;
  latitude: number;
  longitude: number;
  event_time: string;
  source_url: string;
  source_name: string;
}

export interface FlightsResponse {
  count: number;
  flights: MilitaryFlight[];
}

export interface EventsResponse {
  count: number;
  events: ConflictEvent[];
}

export type EventType =
  | "missile_strike"
  | "airstrike"
  | "explosion"
  | "conflict"
  | "troop_movement"
  | "naval_incident"
  | "shelling";

export const EVENT_COLORS: Record<string, string> = {
  missile_strike: "#ff0000",
  airstrike: "#ff4400",
  explosion: "#ff6600",
  conflict: "#ffaa00",
  troop_movement: "#0088ff",
  naval_incident: "#0044cc",
  shelling: "#cc0000",
};

export const EVENT_LABELS: Record<string, string> = {
  missile_strike: "Missile Strike",
  airstrike: "Airstrike",
  explosion: "Explosion",
  conflict: "Conflict",
  troop_movement: "Troop Movement",
  naval_incident: "Naval Incident",
  shelling: "Shelling",
};

export interface Filters {
  showFlights: boolean;
  showEvents: boolean;
  eventTypes: Set<string>;
  timeRangeHours: number;
}
