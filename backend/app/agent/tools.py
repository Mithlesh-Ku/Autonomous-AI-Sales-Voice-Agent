"""Agent tools for ChromaDB RAG lookup, calendar slot checking, demo booking, and CRM upserts."""

import re
from typing import Any, Optional
from langchain_core.tools import tool

from app.db.database import SessionLocal
from app.db.models import Appointment, Lead, utc_now
from app.db.seed import generate_candidate_slots
from app.rag.ingest import query_knowledge_base


def get_available_slots_data(days_ahead: int = 3) -> list[dict[str, Any]]:
    """Return upcoming calendar slots annotated with availability against SQLite appointments."""
    candidates = generate_candidate_slots(days_ahead=days_ahead)
    db = SessionLocal()
    try:
        booked_isos = {
            row.slot_iso
            for row in db.query(Appointment.slot_iso).filter(Appointment.status == "Confirmed").all()
        }
    finally:
        db.close()

    return [
        {**slot, "available": slot["slot_iso"] not in booked_isos}
        for slot in candidates
    ]


def upsert_crm_lead_data(
    bant: dict[str, Any],
    sentiment: str,
    detected_language: str,
    status: Optional[str] = None,
    lead_id: Optional[int] = None,
) -> dict[str, Any]:
    """Create or update a CRM Lead record with English-normalized BANT fields."""
    db = SessionLocal()
    try:
        lead: Optional[Lead] = None
        if lead_id is not None:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if lead is None and bant.get("email"):
            lead = db.query(Lead).filter(Lead.email == bant["email"]).first()
        if lead is None and bant.get("company") and bant.get("name"):
            lead = (
                db.query(Lead)
                .filter(Lead.company == bant["company"], Lead.name == bant["name"])
                .first()
            )

        if lead is None:
            lead = Lead()
            db.add(lead)

        for field in ("name", "email", "company", "role", "budget", "authority", "need", "timeline"):
            val = bant.get(field)
            if val:
                setattr(lead, field, str(val).strip())

        score = int(bant.get("lead_score") or lead.lead_score or 15)
        lead.lead_score = max(0, min(100, score))
        lead.sentiment = sentiment or lead.sentiment or "Neutral"
        lead.detected_language = detected_language or lead.detected_language or "English"

        if status:
            lead.status = status
        elif lead.status != "Demo Booked":
            lead.status = "Qualified" if lead.lead_score >= 65 else "New"

        lead.updated_at = utc_now()
        db.commit()
        db.refresh(lead)
        return {
            "lead_id": lead.id,
            "name": lead.name,
            "company": lead.company,
            "lead_score": lead.lead_score,
            "status": lead.status,
        }
    finally:
        db.close()


def book_appointment_data(
    slot_iso: str,
    lead_name: str,
    company: str,
    email: str,
    notes: str = "",
    lead_id: Optional[int] = None,
) -> dict[str, Any]:
    """Book a demo slot in SQLite if available and mark the CRM lead as Demo Booked."""
    slots = get_available_slots_data(days_ahead=5)
    matching = next((s for s in slots if s["slot_iso"] == slot_iso), None)
    if matching is None:
        # Allow partial date/time match or pick the earliest open slot if caller passed label
        matching = next(
            (s for s in slots if s["available"] and slot_iso.lower() in s["slot_label"].lower()),
            None,
        )
    if matching is None:
        return {"ok": False, "error": f"Slot '{slot_iso}' was not found in calendar availability."}
    if not matching["available"]:
        open_next = [s["slot_label"] for s in slots if s["available"]][:3]
        return {"ok": False, "error": "Slot already booked.", "suggested_slots": open_next}

    db = SessionLocal()
    try:
        lead: Optional[Lead] = None
        if lead_id is not None:
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if lead is None and email:
            lead = db.query(Lead).filter(Lead.email == email).first()
        if lead is None:
            lead = Lead(
                name=lead_name or "Prospect",
                company=company or "Unknown Company",
                email=email or None,
                status="Demo Booked",
                lead_score=80,
            )
            db.add(lead)
            db.flush()
        else:
            if lead_name:
                lead.name = lead_name
            if company:
                lead.company = company
            if email:
                lead.email = email
            lead.status = "Demo Booked"
            lead.lead_score = max(int(lead.lead_score or 0), 80)

        slug = re.sub(r"[^a-z0-9]+", "-", (company or "demo").lower()).strip("-")[:18] or "demo"
        meeting_link = f"https://meet.novaflow.ai/demo-{slug}-{lead.id}"

        appt = Appointment(
            lead_id=lead.id,
            lead_name=lead_name or lead.name,
            company=company or lead.company,
            email=email or lead.email,
            slot_iso=matching["slot_iso"],
            slot_label=matching["slot_label"],
            timezone=matching["timezone"],
            ae_owner=matching["ae_owner"],
            meeting_link=meeting_link,
            status="Confirmed",
            notes=notes or "Booked autonomously by NovaFlow AI Sales Voice Agent.",
        )
        db.add(appt)
        db.commit()
        db.refresh(appt)
        return {
            "ok": True,
            "appointment": {
                "id": appt.id,
                "lead_id": appt.lead_id,
                "lead_name": appt.lead_name,
                "company": appt.company,
                "email": appt.email,
                "slot_iso": appt.slot_iso,
                "slot_label": appt.slot_label,
                "timezone": appt.timezone,
                "ae_owner": appt.ae_owner,
                "meeting_link": appt.meeting_link,
                "status": appt.status,
                "notes": appt.notes,
                "created_at": appt.created_at.isoformat(),
            },
        }
    finally:
        db.close()


@tool
def search_knowledge_base(query: str) -> str:
    """Search NovaFlow AI pricing tiers, product features, integrations, security, and objection playbooks."""
    hits = query_knowledge_base(query, top_k=3)
    if not hits:
        return "No relevant knowledge base entries found."
    formatted = []
    for hit in hits:
        formatted.append(f"[{hit['source']} | {hit['section']}]\n{hit['content']}")
    return "\n\n---\n\n".join(formatted)


@tool
def check_available_slots(days_ahead: int = 3) -> list[dict[str, Any]]:
    """Check open B2B product demo calendar slots over the next few business days."""
    slots = get_available_slots_data(days_ahead=days_ahead)
    return [s for s in slots if s["available"]][:6]


@tool
def book_appointment(
    slot_iso: str,
    lead_name: str,
    company: str,
    email: str,
    notes: str = "",
) -> dict[str, Any]:
    """Book a confirmed product demo slot in the calendar and update the CRM lead status."""
    return book_appointment_data(
        slot_iso=slot_iso,
        lead_name=lead_name,
        company=company,
        email=email,
        notes=notes,
    )


@tool
def upsert_crm_lead(
    name: str = "",
    email: str = "",
    company: str = "",
    role: str = "",
    budget: str = "",
    authority: str = "",
    need: str = "",
    timeline: str = "",
    lead_score: int = 50,
    sentiment: str = "Neutral",
    detected_language: str = "English",
) -> dict[str, Any]:
    """Upsert structured English-normalized BANT lead attributes into the CRM database."""
    bant = {
        "name": name or None,
        "email": email or None,
        "company": company or None,
        "role": role or None,
        "budget": budget or None,
        "authority": authority or None,
        "need": need or None,
        "timeline": timeline or None,
        "lead_score": lead_score,
    }
    return upsert_crm_lead_data(bant=bant, sentiment=sentiment, detected_language=detected_language)


AGENT_TOOLS = [search_knowledge_base, check_available_slots, book_appointment, upsert_crm_lead]
