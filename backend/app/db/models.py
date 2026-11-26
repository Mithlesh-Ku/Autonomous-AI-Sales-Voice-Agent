"""SQLAlchemy ORM models for CRM leads, appointments, call sessions, and insights."""

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=True)
    email = Column(String(180), nullable=True, index=True)
    company = Column(String(160), nullable=True, index=True)
    role = Column(String(120), nullable=True)
    budget = Column(String(160), nullable=True)
    authority = Column(String(160), nullable=True)
    need = Column(Text, nullable=True)
    timeline = Column(String(160), nullable=True)
    lead_score = Column(Integer, default=15, nullable=False)
    sentiment = Column(String(40), default="Neutral", nullable=False)
    detected_language = Column(String(40), default="English", nullable=False)
    status = Column(String(40), default="New", nullable=False)  # New | Qualified | Demo Booked | Nurture
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    appointments = relationship("Appointment", back_populates="lead", cascade="all, delete-orphan")
    call_sessions = relationship("CallSession", back_populates="lead")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)
    lead_name = Column(String(120), nullable=True)
    company = Column(String(160), nullable=True)
    email = Column(String(180), nullable=True)
    slot_iso = Column(String(64), unique=True, nullable=False, index=True)
    slot_label = Column(String(120), nullable=False)
    timezone = Column(String(64), default="America/New_York", nullable=False)
    ae_owner = Column(String(120), default="Elena Rostova (Enterprise AE)", nullable=False)
    meeting_link = Column(String(255), nullable=False)
    status = Column(String(40), default="Confirmed", nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    lead = relationship("Lead", back_populates="appointments")


class CallSession(Base):
    __tablename__ = "call_sessions"

    id = Column(String(64), primary_key=True, index=True)
    mode = Column(String(20), default="inbound", nullable=False)
    status = Column(String(20), default="active", nullable=False)  # active | ended
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)
    detected_language = Column(String(40), default="English", nullable=False)
    sentiment = Column(String(40), default="Neutral", nullable=False)
    bant_json = Column(Text, default="{}", nullable=False)
    transcript_json = Column(Text, default="[]", nullable=False)
    tool_events_json = Column(Text, default="[]", nullable=False)
    started_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    lead = relationship("Lead", back_populates="call_sessions")
    insight = relationship("CallInsight", back_populates="session", uselist=False, cascade="all, delete-orphan")


class CallInsight(Base):
    __tablename__ = "call_insights"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), ForeignKey("call_sessions.id"), unique=True, nullable=False)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True)
    executive_summary = Column(Text, nullable=False)
    key_objections_json = Column(Text, default="[]", nullable=False)
    next_best_action = Column(Text, nullable=False)
    conversion_probability = Column(Integer, default=50, nullable=False)
    sentiment_overall = Column(String(40), default="Neutral", nullable=False)
    detected_language = Column(String(40), default="English", nullable=False)
    lead_score_final = Column(Integer, default=50, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    session = relationship("CallSession", back_populates="insight")
