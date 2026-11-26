"""Pydantic v2 request, response, and agent domain schemas."""

from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

SentimentLabel = Literal["Positive", "Neutral", "Skeptical", "Frustrated", "Ready to Buy"]
CallMode = Literal["inbound", "outbound"]


class BantState(BaseModel):
    """Structured BANT qualification profile normalized in English."""

    name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    budget: Optional[str] = None
    authority: Optional[str] = None
    need: Optional[str] = None
    timeline: Optional[str] = None
    lead_score: int = Field(default=15, ge=0, le=100)


class TranscriptTurn(BaseModel):
    """Single conversational turn in a sales call."""

    role: Literal["user", "assistant", "system"]
    text: str
    language: str = "English"
    timestamp: str
    interrupted: bool = False


class StartCallRequest(BaseModel):
    mode: CallMode = "inbound"
    prospect_name: Optional[str] = None
    company: Optional[str] = None
    language_hint: Optional[str] = None


class ChatTurnRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    language: Optional[str] = None


class LeadOut(BaseModel):
    id: int
    name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    budget: Optional[str] = None
    authority: Optional[str] = None
    need: Optional[str] = None
    timeline: Optional[str] = None
    lead_score: int
    sentiment: str
    detected_language: str
    status: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class AppointmentOut(BaseModel):
    id: int
    lead_id: Optional[int] = None
    lead_name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    slot_iso: str
    slot_label: str
    timezone: str
    ae_owner: str
    meeting_link: str
    status: str
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CalendarSlotOut(BaseModel):
    slot_iso: str
    slot_label: str
    timezone: str
    ae_owner: str
    available: bool


class CallInsightOut(BaseModel):
    id: int
    session_id: str
    lead_id: Optional[int] = None
    lead_name: Optional[str] = None
    company: Optional[str] = None
    executive_summary: str
    key_objections: list[str]
    next_best_action: str
    conversion_probability: int
    sentiment_overall: str
    detected_language: str
    lead_score_final: int
    created_at: datetime


class CallSessionOut(BaseModel):
    id: str
    mode: str
    status: str
    lead_id: Optional[int] = None
    detected_language: str
    sentiment: str
    bant: BantState
    transcript: list[dict[str, Any]]
    tool_events: list[dict[str, Any]]
    started_at: datetime
    ended_at: Optional[datetime] = None


class AgentTurnResponse(BaseModel):
    session_id: str
    assistant_text: str
    detected_language: str
    sentiment: SentimentLabel
    bant: BantState
    tool_events: list[dict[str, Any]]
    rag_sources: list[str]
    tts_provider: str
    audio_base64: Optional[str] = None
    audio_mime: Optional[str] = None
    booked_appointment: Optional[AppointmentOut] = None


class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


class AnalyticsSummaryOut(BaseModel):
    total_leads: int
    qualified_leads: int
    booked_demos: int
    completed_calls: int
    avg_lead_score: float
    avg_conversion_probability: float
    sentiment_breakdown: dict[str, int]
    language_breakdown: dict[str, int]
