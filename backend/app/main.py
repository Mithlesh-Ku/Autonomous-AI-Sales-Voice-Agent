"""FastAPI application entry point exposing REST and WebSocket endpoints for the AI Sales Voice Agent."""

import asyncio
import base64
import json
import uuid
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.orm import Session

from app.agent.graph import sales_agent_graph
from app.agent.tools import get_available_slots_data
from app.config import settings
from app.db.database import SessionLocal, get_db, init_db
from app.db.models import Appointment, CallInsight, CallSession, Lead, utc_now
from app.db.seed import seed_database
from app.rag.ingest import ingest_knowledge_base, query_knowledge_base
from app.schemas import (
    AgentTurnResponse,
    AnalyticsSummaryOut,
    AppointmentOut,
    BantState,
    CalendarSlotOut,
    CallInsightOut,
    CallSessionOut,
    ChatTurnRequest,
    LeadOut,
    StartCallRequest,
    TtsRequest,
)
from app.services.post_call import compute_analytics_summary, generate_post_call_insights
from app.voice.stt_tts import voice_service


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize SQLite schema, seed sample CRM records, and populate ChromaDB on startup."""
    init_db()
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    ingest_knowledge_base(force=False)
    yield


app = FastAPI(
    title="NovaFlow AI — Autonomous Sales Voice Agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _serialize_insight(insight: CallInsight, db: Session) -> CallInsightOut:
    lead = db.query(Lead).filter(Lead.id == insight.lead_id).first() if insight.lead_id else None
    return CallInsightOut(
        id=insight.id,
        session_id=insight.session_id,
        lead_id=insight.lead_id,
        lead_name=lead.name if lead else None,
        company=lead.company if lead else None,
        executive_summary=insight.executive_summary,
        key_objections=json.loads(insight.key_objections_json or "[]"),
        next_best_action=insight.next_best_action,
        conversion_probability=insight.conversion_probability,
        sentiment_overall=insight.sentiment_overall,
        detected_language=insight.detected_language,
        lead_score_final=insight.lead_score_final,
        created_at=insight.created_at,
    )


def _build_greeting(mode: str, prospect_name: Optional[str], company: Optional[str], language_hint: Optional[str]) -> str:
    name_part = f" {prospect_name}" if prospect_name else ""
    company_part = f" at {company}" if company else ""
    if language_hint == "Spanish":
        if mode == "outbound":
            return f"Hola{name_part}, soy Ava de NovaFlow AI. Llamo brevemente porque ayudamos a equipos B2B{company_part} a automatizar su CRM y calificacion de leads. Tienes dos minutos?"
        return f"Hola{name_part}, gracias por comunicarte con NovaFlow AI. Soy Ava, en que puedo ayudarte hoy?"
    if language_hint == "Hindi":
        if mode == "outbound":
            return f"Namaste{name_part}, main Ava bol rahi hoon NovaFlow AI se. Hum B2B teams{company_part} ki lead qualification aur CRM automation mein madad karte hain. Kya aapke paas do minute hain?"
        return f"Namaste{name_part}, NovaFlow AI mein aapka swagat hai. Main Ava hoon—aaj main aapki kaise madad kar sakti hoon?"
    if mode == "outbound":
        return (
            f"Hi{name_part}, this is Ava calling from NovaFlow AI. I'm reaching out to revenue teams{company_part} "
            "who want to eliminate manual CRM hygiene and qualify inbound leads in real time. Got a quick minute to share what your team uses today?"
        )
    return (
        f"Hi{name_part}, thanks for calling NovaFlow AI! I'm Ava, your AI sales specialist. "
        "What caught your eye about automating your revenue workflows today?"
    )


async def _process_agent_turn(
    session_id: str,
    user_text: str,
    db: Session,
    language_hint: Optional[str] = None,
) -> AgentTurnResponse:
    """Execute one stateful LangGraph turn, persist session artifacts, and synthesize TTS."""
    session = db.query(CallSession).filter(CallSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Call session not found")
    if session.status == "ended":
        raise HTTPException(status_code=400, detail="Call session has already ended")

    transcript: list[dict[str, Any]] = json.loads(session.transcript_json or "[]")
    tool_events_hist: list[dict[str, Any]] = json.loads(session.tool_events_json or "[]")
    current_bant = json.loads(session.bant_json or "{}")

    transcript.append(
        {
            "role": "user",
            "text": user_text,
            "language": language_hint or session.detected_language,
            "timestamp": utc_now().isoformat(),
        }
    )

    graph_input = {
        "session_id": session_id,
        "mode": session.mode,
        "lead_id": session.lead_id,
        "messages": [HumanMessage(content=user_text)],
        "detected_language": language_hint or session.detected_language,
        "sentiment": session.sentiment,
        "bant": current_bant,
        "rag_sources": [],
        "tool_events": [],
        "booked_appointment": None,
        "assistant_reply": "",
    }
    config = {"configurable": {"thread_id": session_id}}
    result = await sales_agent_graph.ainvoke(graph_input, config=config)

    reply_text = result.get("assistant_reply") or "Could you tell me a bit more about your team's workflow?"
    detected_lang = result.get("detected_language") or "English"
    sentiment = result.get("sentiment") or "Neutral"
    bant_dict = result.get("bant") or current_bant
    new_tool_events = result.get("tool_events") or []
    rag_sources = result.get("rag_sources") or []
    booked_appt = result.get("booked_appointment")

    transcript.append(
        {
            "role": "assistant",
            "text": reply_text,
            "language": detected_lang,
            "timestamp": utc_now().isoformat(),
        }
    )
    tool_events_hist.extend(new_tool_events)

    session.lead_id = result.get("lead_id") or session.lead_id
    session.detected_language = detected_lang
    session.sentiment = sentiment
    session.bant_json = json.dumps(bant_dict)
    session.transcript_json = json.dumps(transcript)
    session.tool_events_json = json.dumps(tool_events_hist)
    db.commit()

    tts_out = await voice_service.synthesize_speech(reply_text)
    bant_model = BantState(**{k: bant_dict.get(k) for k in BantState.model_fields})

    appt_model: Optional[AppointmentOut] = None
    if booked_appt:
        appt_row = db.query(Appointment).filter(Appointment.id == booked_appt["id"]).first()
        if appt_row:
            appt_model = AppointmentOut.model_validate(appt_row)

    return AgentTurnResponse(
        session_id=session_id,
        assistant_text=reply_text,
        detected_language=detected_lang,
        sentiment=sentiment,  # type: ignore[arg-type]
        bant=bant_model,
        tool_events=new_tool_events,
        rag_sources=rag_sources,
        tts_provider=tts_out["provider"],
        audio_base64=tts_out["audio_base64"],
        audio_mime=tts_out["audio_mime"],
        booked_appointment=appt_model,
    )


async def _run_post_call_background(session_id: str) -> None:
    """Async background task that runs post-call summarization with its own DB session."""
    db = SessionLocal()
    try:
        await generate_post_call_insights(session_id, db)
    finally:
        db.close()


@app.get("/")
def root() -> dict[str, str]:
    """Friendly root response pointing evaluators to the frontend UI and API docs."""
    return {
        "service": "NovaFlow AI — Autonomous Sales Voice Agent API",
        "frontend_ui": "http://localhost:5173",
        "swagger_docs": "http://127.0.0.1:8000/docs",
        "health": "http://127.0.0.1:8000/api/health",
    }


@app.get("/api/health")
def health_check() -> dict[str, Any]:
    """Report runtime status and active provider configuration (never exposing secrets)."""
    kb_count = ingest_knowledge_base(force=False)
    return {
        "status": "ok",
        "llm_provider": settings.resolved_llm_provider(),
        "stt_provider": settings.resolved_stt_provider(),
        "tts_provider": settings.resolved_tts_provider(),
        "kb_chunks": kb_count,
    }


@app.post("/api/calls/start")
async def start_call(payload: StartCallRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Create a new sales call session and return the AI opening greeting."""
    session_id = f"call-{uuid.uuid4().hex[:10]}"
    lang = payload.language_hint or "English"
    greeting = _build_greeting(payload.mode, payload.prospect_name, payload.company, payload.language_hint)

    initial_bant = BantState(
        name=payload.prospect_name,
        company=payload.company,
        lead_score=15,
    ).model_dump()

    transcript = [
        {
            "role": "assistant",
            "text": greeting,
            "language": lang,
            "timestamp": utc_now().isoformat(),
        }
    ]
    session = CallSession(
        id=session_id,
        mode=payload.mode,
        status="active",
        detected_language=lang,
        sentiment="Neutral",
        bant_json=json.dumps(initial_bant),
        transcript_json=json.dumps(transcript),
        tool_events_json="[]",
    )
    db.add(session)
    db.commit()

    # Seed LangGraph checkpoint with the opening assistant turn
    await sales_agent_graph.aupdate_state(
        {"configurable": {"thread_id": session_id}},
        {
            "session_id": session_id,
            "mode": payload.mode,
            "lead_id": None,
            "messages": [AIMessage(content=greeting)],
            "detected_language": lang,
            "sentiment": "Neutral",
            "bant": initial_bant,
            "rag_sources": [],
            "tool_events": [],
            "booked_appointment": None,
            "assistant_reply": greeting,
        },
    )

    tts_out = await voice_service.synthesize_speech(greeting)
    return {
        "session_id": session_id,
        "mode": payload.mode,
        "greeting": greeting,
        "detected_language": lang,
        "sentiment": "Neutral",
        "bant": initial_bant,
        "tts_provider": tts_out["provider"],
        "audio_base64": tts_out["audio_base64"],
        "audio_mime": tts_out["audio_mime"],
    }


@app.post("/api/calls/{session_id}/turn", response_model=AgentTurnResponse)
async def submit_call_turn(
    session_id: str,
    payload: ChatTurnRequest,
    db: Session = Depends(get_db),
) -> AgentTurnResponse:
    """REST endpoint for text-fallback or test turns during a live call."""
    return await _process_agent_turn(session_id, payload.text, db, language_hint=payload.language)


@app.post("/api/calls/{session_id}/end")
async def end_call(
    session_id: str,
    background_tasks: BackgroundTasks,
    wait: bool = Query(default=True, description="Await insight generation before returning"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """End an active call session and trigger the post-call insights pipeline."""
    session = db.query(CallSession).filter(CallSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Call session not found")

    session.status = "ended"
    session.ended_at = session.ended_at or utc_now()
    db.commit()

    if wait:
        insight = await generate_post_call_insights(session_id, db)
        return {
            "status": "completed",
            "session_id": session_id,
            "insight": _serialize_insight(insight, db).model_dump(mode="json"),
        }

    background_tasks.add_task(_run_post_call_background, session_id)
    return {"status": "processing", "session_id": session_id}


@app.get("/api/calls/{session_id}", response_model=CallSessionOut)
def get_call_session(session_id: str, db: Session = Depends(get_db)) -> CallSessionOut:
    """Retrieve full state, transcript, and tool events for a call session."""
    session = db.query(CallSession).filter(CallSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Call session not found")

    bant_raw = json.loads(session.bant_json or "{}")
    return CallSessionOut(
        id=session.id,
        mode=session.mode,
        status=session.status,
        lead_id=session.lead_id,
        detected_language=session.detected_language,
        sentiment=session.sentiment,
        bant=BantState(**{k: bant_raw.get(k) for k in BantState.model_fields}),
        transcript=json.loads(session.transcript_json or "[]"),
        tool_events=json.loads(session.tool_events_json or "[]"),
        started_at=session.started_at,
        ended_at=session.ended_at,
    )


@app.websocket("/ws/call/{session_id}")
async def call_websocket(websocket: WebSocket, session_id: str) -> None:
    """Bidirectional WebSocket handling real-time transcript turns, audio STT, and barge-in."""
    await websocket.accept()
    active_turn_task: Optional[asyncio.Task[Any]] = None

    async def handle_turn_and_emit(user_text: str, lang_hint: Optional[str]) -> None:
        db = SessionLocal()
        try:
            turn_res = await _process_agent_turn(session_id, user_text, db, language_hint=lang_hint)
            await websocket.send_json(
                {
                    "type": "agent_turn",
                    "data": turn_res.model_dump(mode="json"),
                }
            )
        except asyncio.CancelledError:
            await websocket.send_json({"type": "interrupted", "reason": "barge_in"})
            raise
        except Exception as exc:
            await websocket.send_json({"type": "error", "detail": str(exc)})
        finally:
            db.close()

    try:
        await websocket.send_json({"type": "connected", "session_id": session_id})
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type")

            if msg_type == "barge_in":
                if active_turn_task and not active_turn_task.done():
                    active_turn_task.cancel()
                await websocket.send_json({"type": "interrupted", "reason": "client_barge_in"})
                continue

            if msg_type == "user_text":
                text = (msg.get("text") or "").strip()
                if not text:
                    continue
                if active_turn_task and not active_turn_task.done():
                    active_turn_task.cancel()
                active_turn_task = asyncio.create_task(handle_turn_and_emit(text, msg.get("language")))
                continue

            if msg_type == "audio_chunk":
                raw_b64 = msg.get("audio_base64") or ""
                mime = msg.get("mime_type") or "audio/webm"
                if raw_b64:
                    audio_bytes = base64.b64decode(raw_b64)
                    stt_res = await voice_service.transcribe_audio(audio_bytes, mime_type=mime)
                    await websocket.send_json({"type": "stt_result", "data": stt_res})
                    if stt_res.get("text"):
                        if active_turn_task and not active_turn_task.done():
                            active_turn_task.cancel()
                        active_turn_task = asyncio.create_task(
                            handle_turn_and_emit(stt_res["text"], stt_res.get("language"))
                        )
                continue

            if msg_type == "end_call":
                if active_turn_task and not active_turn_task.done():
                    active_turn_task.cancel()
                db = SessionLocal()
                try:
                    insight = await generate_post_call_insights(session_id, db)
                    await websocket.send_json(
                        {
                            "type": "insights_ready",
                            "data": _serialize_insight(insight, db).model_dump(mode="json"),
                        }
                    )
                finally:
                    db.close()
                break
    except WebSocketDisconnect:
        if active_turn_task and not active_turn_task.done():
            active_turn_task.cancel()


@app.post("/api/voice/stt")
async def voice_stt(
    file: UploadFile = File(...),
    language_hint: Optional[str] = None,
) -> dict[str, Any]:
    """Transcribe an audio clip via Deepgram, or return browser fallback signal."""
    audio_bytes = await file.read()
    return await voice_service.transcribe_audio(
        audio_bytes=audio_bytes,
        mime_type=file.content_type or "audio/webm",
        language_hint=language_hint,
    )


@app.post("/api/voice/tts")
async def voice_tts(payload: TtsRequest) -> dict[str, Any]:
    """Synthesize spoken audio using configured TTS provider or browser fallback."""
    return await voice_service.synthesize_speech(payload.text)


@app.get("/api/leads", response_model=list[LeadOut])
def list_leads(db: Session = Depends(get_db)) -> list[LeadOut]:
    """Return all CRM leads ordered by most recently updated."""
    rows = db.query(Lead).order_by(Lead.updated_at.desc()).all()
    return [LeadOut.model_validate(r) for r in rows]


@app.get("/api/appointments", response_model=list[AppointmentOut])
def list_appointments(db: Session = Depends(get_db)) -> list[AppointmentOut]:
    """Return all scheduled product demo appointments."""
    rows = db.query(Appointment).order_by(Appointment.slot_iso.asc()).all()
    return [AppointmentOut.model_validate(r) for r in rows]


@app.get("/api/appointments/slots", response_model=list[CalendarSlotOut])
def list_calendar_slots(days_ahead: int = Query(default=4, ge=1, le=10)) -> list[CalendarSlotOut]:
    """Return upcoming AE calendar slots with live availability."""
    return [CalendarSlotOut(**s) for s in get_available_slots_data(days_ahead=days_ahead)]


@app.get("/api/insights", response_model=list[CallInsightOut])
def list_insights(db: Session = Depends(get_db)) -> list[CallInsightOut]:
    """Return generated post-call business insights newest first."""
    rows = db.query(CallInsight).order_by(CallInsight.created_at.desc()).all()
    return [_serialize_insight(r, db) for r in rows]


@app.get("/api/analytics", response_model=AnalyticsSummaryOut)
def get_analytics(db: Session = Depends(get_db)) -> AnalyticsSummaryOut:
    """Return aggregated CRM and call conversion metrics for the admin dashboard."""
    return AnalyticsSummaryOut(**compute_analytics_summary(db))


@app.post("/api/rag/query")
def query_rag(payload: ChatTurnRequest) -> dict[str, Any]:
    """Inspect ChromaDB knowledge retrieval results directly for debugging/live-coding."""
    return {"query": payload.text, "results": query_knowledge_base(payload.text, top_k=3)}
