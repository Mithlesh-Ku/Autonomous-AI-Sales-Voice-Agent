"""Asynchronous post-call summarization, insight extraction, and CRM analytics service."""

import json
import re
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from app.db.models import Appointment, CallInsight, CallSession, Lead, utc_now
from app.llm.factory import get_chat_model

INSIGHT_PROMPT = """You are a Revenue Operations analyst reviewing a finished B2B SaaS sales call transcript.
Return ONLY valid JSON with:
{
  "executive_summary": "2-3 sentence executive summary in English",
  "key_objections": ["list of concise objections raised, or empty list"],
  "next_best_action": "single concrete next step for the Account Executive",
  "conversion_probability": integer 0-100
}"""


def _deterministic_insights(
    transcript: list[dict[str, Any]],
    bant: dict[str, Any],
    sentiment: str,
    has_booking: bool,
) -> dict[str, Any]:
    """Generate structured post-call insights cleanly even in offline/mock mode."""
    prospect_lines = [t.get("text", "") for t in transcript if t.get("role") == "user"]
    combined = " ".join(prospect_lines).lower()

    objections: list[str] = []
    if any(w in combined for w in ("expensive", "budget", "cost", "price", "mahanga", "caro")):
        objections.append("Pricing / budget ROI scrutiny")
    if any(w in combined for w in ("soc 2", "security", "gdpr", "privacy", "infosec")):
        objections.append("InfoSec, SOC 2 Type II & data privacy verification")
    if any(w in combined for w in ("already use", "salesforce", "gong", "hubspot")):
        objections.append("Overlap with existing CRM / call recording stack")
    if any(w in combined for w in ("long", "implement", "migration", "vp")):
        objections.append("Implementation timeline & executive stakeholder alignment")

    score = int(bant.get("lead_score") or 30)
    prob = min(95, max(15, score + (12 if has_booking else -5)))
    if sentiment == "Ready to Buy":
        prob = max(prob, 82)
    elif sentiment == "Frustrated":
        prob = min(prob, 25)

    name = bant.get("name") or "The prospect"
    company = bant.get("company") or "their organization"
    need = bant.get("need") or "workflow & CRM automation"
    summary = (
        f"{name} from {company} discussed {need}. "
        f"Final qualification score reached {score}/100 with '{sentiment}' sentiment"
        + (" and a confirmed product demo booked." if has_booking else ", pending follow-up demo scheduling.")
    )

    if has_booking:
        next_action = "Send tailored architecture brief & ROI calculator 24 hours before the scheduled AE demo."
    elif objections:
        next_action = f"Address '{objections[0]}' with a 1-page proof packet and propose two 20-min demo slots."
    else:
        next_action = "Follow up via email with Growth tier ROI summary and calendar booking link."

    return {
        "executive_summary": summary,
        "key_objections": objections,
        "next_best_action": next_action,
        "conversion_probability": int(prob),
    }


async def generate_post_call_insights(session_id: str, db: Session) -> CallInsight:
    """Close a call session, synthesize executive insights, and persist to SQLite."""
    session = db.query(CallSession).filter(CallSession.id == session_id).first()
    if session is None:
        raise ValueError(f"Call session '{session_id}' not found.")

    if session.insight is not None:
        return session.insight

    transcript = json.loads(session.transcript_json or "[]")
    bant = json.loads(session.bant_json or "{}")
    has_booking = False
    if session.lead_id:
        has_booking = db.query(Appointment).filter(Appointment.lead_id == session.lead_id).count() > 0

    insight_data = _deterministic_insights(
        transcript=transcript,
        bant=bant,
        sentiment=session.sentiment,
        has_booking=has_booking,
    )

    llm = get_chat_model(temperature=0.2)
    if llm is not None and transcript:
        formatted_tx = "\n".join(f"{t.get('role', 'user').upper()}: {t.get('text', '')}" for t in transcript)
        try:
            resp = await llm.ainvoke(
                [
                    SystemMessage(content=INSIGHT_PROMPT),
                    HumanMessage(
                        content=(
                            f"BANT: {json.dumps(bant)}\nSentiment: {session.sentiment}\n"
                            f"Demo Booked: {has_booking}\n\nTranscript:\n{formatted_tx}"
                        )
                    ),
                ]
            )
            match = re.search(r"\{[\s\S]*\}", str(resp.content))
            if match:
                parsed = json.loads(match.group(0))
                if parsed.get("executive_summary"):
                    insight_data["executive_summary"] = str(parsed["executive_summary"])
                if isinstance(parsed.get("key_objections"), list):
                    insight_data["key_objections"] = [str(o) for o in parsed["key_objections"]]
                if parsed.get("next_best_action"):
                    insight_data["next_best_action"] = str(parsed["next_best_action"])
                if isinstance(parsed.get("conversion_probability"), (int, float)):
                    insight_data["conversion_probability"] = max(0, min(100, int(parsed["conversion_probability"])))
        except Exception:
            pass

    session.status = "ended"
    session.ended_at = session.ended_at or utc_now()

    insight = CallInsight(
        session_id=session.id,
        lead_id=session.lead_id,
        executive_summary=insight_data["executive_summary"],
        key_objections_json=json.dumps(insight_data["key_objections"]),
        next_best_action=insight_data["next_best_action"],
        conversion_probability=insight_data["conversion_probability"],
        sentiment_overall=session.sentiment,
        detected_language=session.detected_language,
        lead_score_final=int(bant.get("lead_score") or 15),
    )
    db.add(insight)
    db.commit()
    db.refresh(insight)
    return insight


def compute_analytics_summary(db: Session) -> dict[str, Any]:
    """Aggregate live CRM & post-call metrics for the admin dashboard."""
    leads = db.query(Lead).all()
    insights = db.query(CallInsight).all()
    appointments_count = db.query(Appointment).filter(Appointment.status == "Confirmed").count()

    total_leads = len(leads)
    qualified_leads = sum(1 for l in leads if l.lead_score >= 65 or l.status in ("Qualified", "Demo Booked"))
    avg_lead_score = round(sum(l.lead_score for l in leads) / total_leads, 1) if total_leads else 0.0
    avg_conv = round(sum(i.conversion_probability for i in insights) / len(insights), 1) if insights else 0.0

    sentiment_breakdown: dict[str, int] = {}
    language_breakdown: dict[str, int] = {}
    for lead in leads:
        sentiment_breakdown[lead.sentiment] = sentiment_breakdown.get(lead.sentiment, 0) + 1
        language_breakdown[lead.detected_language] = language_breakdown.get(lead.detected_language, 0) + 1

    return {
        "total_leads": total_leads,
        "qualified_leads": qualified_leads,
        "booked_demos": appointments_count,
        "completed_calls": len(insights),
        "avg_lead_score": avg_lead_score,
        "avg_conversion_probability": avg_conv,
        "sentiment_breakdown": sentiment_breakdown,
        "language_breakdown": language_breakdown,
    }
