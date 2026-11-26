"""Idempotent database seeding with realistic B2B SaaS leads, booked slots, and call insights."""

import json
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.db.models import Appointment, CallInsight, CallSession, Lead


def generate_candidate_slots(days_ahead: int = 4) -> list[dict[str, str]]:
    """Generate upcoming weekday demo slots in EST/EDT for AE availability."""
    now = datetime.now(timezone.utc)
    slots: list[dict[str, str]] = []
    ae_rotation = [
        "Elena Rostova (Enterprise AE)",
        "Marcus Vance (Mid-Market AE)",
    ]
    hour_blocks = [(14, 30, "9:30 AM EST"), (16, 0, "11:00 AM EST"), (19, 0, "2:00 PM EST"), (21, 0, "4:00 PM EST")]

    day_cursor = now + timedelta(days=1)
    added_days = 0
    while added_days < days_ahead:
        if day_cursor.weekday() < 5:  # Monday-Friday
            for idx, (utc_hour, utc_min, est_label) in enumerate(hour_blocks):
                slot_dt = day_cursor.replace(hour=utc_hour, minute=utc_min, second=0, microsecond=0)
                slot_iso = slot_dt.strftime("%Y-%m-%dT%H:%M:00Z")
                date_str = slot_dt.strftime("%a, %b %d")
                slots.append(
                    {
                        "slot_iso": slot_iso,
                        "slot_label": f"{date_str} at {est_label}",
                        "timezone": "America/New_York",
                        "ae_owner": ae_rotation[(added_days + idx) % len(ae_rotation)],
                    }
                )
            added_days += 1
        day_cursor += timedelta(days=1)
    return slots


def seed_database(db: Session) -> None:
    """Populate realistic sample CRM records on initial launch without duplicating rows."""
    if db.query(Lead).count() > 0:
        return

    now = datetime.now(timezone.utc)
    candidate_slots = generate_candidate_slots(days_ahead=4)

    leads = [
        Lead(
            name="Sarah Jenkins",
            email="s.jenkins@finscale.io",
            company="FinScale Technologies",
            role="VP of Revenue Operations",
            budget="$45,000/yr approved",
            authority="Final decision maker with CFO sign-off",
            need="Automate Salesforce lead routing and eliminate 8 hrs/wk of rep CRM hygiene across 40 AEs",
            timeline="Go-live before Q1 kickoff (within 30 days)",
            lead_score=91,
            sentiment="Ready to Buy",
            detected_language="English",
            status="Demo Booked",
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=2),
        ),
        Lead(
            name="Carlos Mendoza",
            email="cmendoza@veloxcloud.es",
            company="VeloxCloud LatAm",
            role="Head of Sales Enablement",
            budget="$18,000/yr",
            authority="Influencer; VP of Sales holds final sign-off",
            need="Multilingual Spanish/English call qualification synced into HubSpot",
            timeline="Evaluating over next 60 days",
            lead_score=74,
            sentiment="Positive",
            detected_language="Spanish",
            status="Qualified",
            created_at=now - timedelta(days=1, hours=5),
            updated_at=now - timedelta(days=1, hours=5),
        ),
        Lead(
            name="Rohan Kulkarni",
            email="rohan@paypulse.in",
            company="PayPulse Fintech",
            role="Director of Inside Sales",
            budget="Evaluating Growth tier ($99/seat)",
            authority="Co-decision maker with CTO for security review",
            need="SOC 2 compliant AI call scoring + faster inbound lead response",
            timeline="Pilot planned next quarter",
            lead_score=64,
            sentiment="Skeptical",
            detected_language="Hindi",
            status="Nurture",
            created_at=now - timedelta(hours=14),
            updated_at=now - timedelta(hours=14),
        ),
    ]
    db.add_all(leads)
    db.flush()

    # Pre-book 2 slots so calendar reflects realistic partial availability
    booked_slot_1 = candidate_slots[0]
    booked_slot_2 = candidate_slots[4]

    appointments = [
        Appointment(
            lead_id=leads[0].id,
            lead_name=leads[0].name,
            company=leads[0].company,
            email=leads[0].email,
            slot_iso=booked_slot_1["slot_iso"],
            slot_label=booked_slot_1["slot_label"],
            timezone=booked_slot_1["timezone"],
            ae_owner=booked_slot_1["ae_owner"],
            meeting_link="https://meet.novaflow.ai/demo-finscale-901",
            status="Confirmed",
            notes="Deep dive on Salesforce Enterprise sync + Snowflake warehouse connector.",
        ),
        Appointment(
            lead_id=leads[1].id,
            lead_name=leads[1].name,
            company=leads[1].company,
            email=leads[1].email,
            slot_iso=booked_slot_2["slot_iso"],
            slot_label=booked_slot_2["slot_label"],
            timezone=booked_slot_2["timezone"],
            ae_owner=booked_slot_2["ae_owner"],
            meeting_link="https://meet.novaflow.ai/demo-velox-412",
            status="Confirmed",
            notes="Bilingual Spanish/English HubSpot qualification walkthrough.",
        ),
    ]
    db.add_all(appointments)

    sample_sessions = [
        CallSession(
            id="seed-session-finscale",
            mode="inbound",
            status="ended",
            lead_id=leads[0].id,
            detected_language="English",
            sentiment="Ready to Buy",
            bant_json=json.dumps(
                {
                    "name": leads[0].name,
                    "email": leads[0].email,
                    "company": leads[0].company,
                    "role": leads[0].role,
                    "budget": leads[0].budget,
                    "authority": leads[0].authority,
                    "need": leads[0].need,
                    "timeline": leads[0].timeline,
                    "lead_score": 91,
                }
            ),
            transcript_json=json.dumps(
                [
                    {
                        "role": "assistant",
                        "text": "Hi Sarah, thanks for calling NovaFlow AI! What sparked your interest in automating your RevOps workflows today?",
                        "language": "English",
                        "timestamp": (now - timedelta(days=2)).isoformat(),
                    },
                    {
                        "role": "user",
                        "text": "We have 40 AEs at FinScale wasting 8 hours a week updating Salesforce. Our Q1 budget of $45k is approved if you integrate cleanly.",
                        "language": "English",
                        "timestamp": (now - timedelta(days=2)).isoformat(),
                    },
                ]
            ),
            tool_events_json=json.dumps(
                [
                    {"tool": "search_knowledge_base", "summary": "Retrieved Growth/Enterprise pricing & Salesforce OAuth specs"},
                    {"tool": "book_appointment", "summary": f"Booked {booked_slot_1['slot_label']}"},
                ]
            ),
            started_at=now - timedelta(days=2),
            ended_at=now - timedelta(days=2) + timedelta(minutes=6),
        ),
        CallSession(
            id="seed-session-paypulse",
            mode="outbound",
            status="ended",
            lead_id=leads[2].id,
            detected_language="Hindi",
            sentiment="Skeptical",
            bant_json=json.dumps(
                {
                    "name": leads[2].name,
                    "email": leads[2].email,
                    "company": leads[2].company,
                    "role": leads[2].role,
                    "budget": leads[2].budget,
                    "authority": leads[2].authority,
                    "need": leads[2].need,
                    "timeline": leads[2].timeline,
                    "lead_score": 64,
                }
            ),
            transcript_json=json.dumps(
                [
                    {
                        "role": "user",
                        "text": "Humein SOC 2 compliance aur data privacy ke baare mein surety chahiye before we test any AI tool.",
                        "language": "Hindi",
                        "timestamp": (now - timedelta(hours=14)).isoformat(),
                    }
                ]
            ),
            tool_events_json=json.dumps(
                [{"tool": "search_knowledge_base", "summary": "Retrieved SOC 2 Type II & PII redaction specs"}]
            ),
            started_at=now - timedelta(hours=14),
            ended_at=now - timedelta(hours=14) + timedelta(minutes=5),
        ),
    ]
    db.add_all(sample_sessions)

    insights = [
        CallInsight(
            session_id="seed-session-finscale",
            lead_id=leads[0].id,
            executive_summary="Sarah Jenkins (VP RevOps, FinScale) has an approved $45k budget for 40 AEs and wants to eliminate manual Salesforce hygiene before Q1. Demo booked with Elena Rostova.",
            key_objections_json=json.dumps(["Needed confirmation of bi-directional Salesforce Enterprise API & Snowflake sync"]),
            next_best_action="Send Salesforce OAuth architecture one-pager ahead of Thursday's live technical demo.",
            conversion_probability=86,
            sentiment_overall="Ready to Buy",
            detected_language="English",
            lead_score_final=91,
        ),
        CallInsight(
            session_id="seed-session-paypulse",
            lead_id=leads[2].id,
            executive_summary="Rohan Kulkarni (PayPulse Fintech) engaged in Hindi regarding inbound AI qualification for 25 inside sales reps, but raised InfoSec/SOC 2 concerns requiring CTO review.",
            key_objections_json=json.dumps(["SOC 2 Type II verification and PII redaction guarantees", "Requires CTO InfoSec sign-off"]),
            next_best_action="Email SOC 2 Type II trust report + schedule 20-min InfoSec alignment call with CTO.",
            conversion_probability=58,
            sentiment_overall="Skeptical",
            detected_language="Hindi",
            lead_score_final=64,
        ),
    ]
    db.add_all(insights)
    db.commit()
