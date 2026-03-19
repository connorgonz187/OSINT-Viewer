from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, func
)
from sqlalchemy.orm import DeclarativeBase
from geoalchemy2 import Geometry


class Base(DeclarativeBase):
    pass


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    event_type = Column(String(50), nullable=False, index=True)
    title = Column(Text, nullable=False)
    summary = Column(Text)
    location_name = Column(String(255))
    coordinates = Column(Geometry("POINT", srid=4326))
    latitude = Column(Float)
    longitude = Column(Float)
    event_time = Column(DateTime(timezone=True), index=True)
    source_url = Column(Text)
    source_name = Column(String(100))
    raw_text = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FlightTrack(Base):
    __tablename__ = "flight_tracks"

    id = Column(Integer, primary_key=True)
    icao24 = Column(String(10), nullable=False, index=True)
    callsign = Column(String(20))
    latitude = Column(Float)
    longitude = Column(Float)
    altitude = Column(Float)
    velocity = Column(Float)
    heading = Column(Float)
    on_ground = Column(Boolean, default=False)
    coordinates = Column(Geometry("POINT", srid=4326))
    seen_at = Column(DateTime(timezone=True), server_default=func.now())


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    url = Column(Text, nullable=False)
    source_type = Column(String(50), nullable=False)
    enabled = Column(Boolean, default=True)
    last_fetched = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
