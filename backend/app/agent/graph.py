"""LangGraph multi-turn sales agent workflow with BANT qualification, RAG, and booking."""

import json
import re
from typing import Any, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.state import SalesAgentState
from app.agent.tools import (
    AGENT_TOOLS,
    book_appointment_data,
    get_available_slots_data,
    upsert_crm_lead_data,
)
from app.llm.factory import get_chat_model
from app.rag.ingest import query_knowledge_base

SYSTEM_PROMPT = """You are Ava, an elite Autonomous B2B SaaS Sales Voice Agent representing NovaFlow AI (an AI Revenue & Workflow Automation Platform).

Your goals on every live call:
1. Respond naturally, warmly, and concisely (2-4 spoken sentences max, no markdown bullets or asterisks) so your response sounds great when read aloud via TTS.
2. MULTILINGUAL RULE: Detect the prospect's language (e.g., English, Hindi, Spanish, French, German) and reply fluently in THAT SAME language. Always keep CRM tool arguments normalized in English.
3. RAG RULE: Before answering any question about pricing, plans, Salesforce/HubSpot integrations, SOC 2 security, ROI, or objections, ALWAYS call `search_knowledge_base` first and ground your answer in the retrieved facts.
4. BANT QUALIFICATION: Naturally uncover Budget, Authority, Need, and Timeline (plus Name, Role, Company, Email) without sounding like a rigid interrogation.
5. BOOKING RULE: When the prospect expresses interest in a demo or has strong fit, call `check_available_slots` and propose 2 specific open times. Once they confirm a time (and share their name + email, or you ask for missing details), call `book_appointment` immediately and confirm the meeting link and AE owner.
"""

BANT_EXTRACTOR_PROMPT = """Analyze the conversation and return ONLY valid JSON with these exact keys (all string values normalized to English, or null if unknown):
{
  "detected_language": "English|Spanish|Hindi|French|German|Portuguese",
  "sentiment": "Positive|Neutral|Skeptical|Frustrated|Ready to Buy",
  "bant": {
    "name": string or null,
    "email": string or null,
    "company": string or null,
    "role": string or null,
    "budget": string or null,
    "authority": string or null,
    "need": string or null,
    "timeline": string or null,
    "lead_score": integer 0-100
  }
}"""


def _detect_language_heuristic(text: str) -> str:
    if re.search(r"[\u0900-\u097f]", text):
        return "Hindi"
    lowered = f" {text.lower()} "
    hindi_markers = (" namaste ", " kaise ", " chahiye ", " humein ", " humara ", " kitna ", " paisa ", " demo chahiye ", " baat ")
    spanish_markers = (" hola ", " gracias ", " precio ", " cuanto ", " queremos ", " necesito ", " reunion ", " demostracion ", " somos ")
    french_markers = (" bonjour ", " merci ", " combien ", " nous ", " besoin ", " tarif ")
    if any(m in lowered for m in hindi_markers):
        return "Hindi"
    if any(m in lowered for m in spanish_markers) or re.search(r"[áéíóúñ¿¡]", text.lower()):
        return "Spanish"
    if any(m in lowered for m in french_markers):
        return "French"
    return "English"


def _classify_sentiment_heuristic(text: str, current_score: int) -> str:
    lower = text.lower()
    if any(w in lower for w in ("book", "schedule", "sign up", "let's do it", "ready", "send the invite", "slot", "thursday", "tomorrow")):
        return "Ready to Buy"
    if any(w in lower for w in ("frustrated", "annoying", "waste of time", "stop", "terrible", "useless", "not working")):
        return "Frustrated"
    if any(w in lower for w in ("expensive", "too much", "already use", "not sure", "skeptical", "soc 2", "privacy", "concern", "doubt", "mahanga")):
        return "Skeptical"
    if any(w in lower for w in ("great", "awesome", "love", "interested", "sounds good", "helpful", "nice", "perfect", "gracias", "shukriya")):
        return "Positive"
    return "Positive" if current_score >= 70 else "Neutral"


def _extract_bant_heuristic(text: str, existing: dict[str, Any]) -> dict[str, Any]:
    bant = dict(existing)
    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    if email_match:
        bant["email"] = email_match.group(0)

    name_match = re.search(r"(?:my name is|i'm|i am|this is|naam)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text, re.IGNORECASE)
    if name_match and not any(w in name_match.group(1).lower() for w in ("looking", "interested", "from", "calling", "trying")):
        bant["name"] = name_match.group(1).title()

    company_match = re.search(
        r"(?:from|at|company is|company)\s+([A-Z][A-Za-z0-9&\.\-]*(?:\s+(?:[A-Z][A-Za-z0-9&\.\-]*|Inc\.?|LLC|Ltd\.?|AI|Corp\.?)){0,3})",
        text,
    )
    if company_match and not bant.get("company"):
        bant["company"] = company_match.group(1).strip()

    role_match = re.search(r"(VP of [A-Za-z ]+|Head of [A-Za-z ]+|Director of [A-Za-z ]+|CTO|CEO|CRO|RevOps Lead|Sales Manager)", text, re.IGNORECASE)
    if role_match:
        bant["role"] = role_match.group(1).strip()

    budget_match = re.search(r"(\$[\d,]+(?:\s*[kKmM])?(?:\s*/\s*(?:yr|year|mo|month))?|\d+\s+seats|\d+\s+reps|\d+\s+AEs)", text, re.IGNORECASE)
    if budget_match:
        bant["budget"] = budget_match.group(1).strip()

    if any(w in text.lower() for w in ("decision maker", "i decide", "my budget", "sign off", "vp", "cto", "cro", "ceo")):
        bant["authority"] = bant.get("authority") or "Key decision maker / leadership stakeholder"
    elif any(w in text.lower() for w in ("check with my", "talk to my vp", "boss", "committee")):
        bant["authority"] = bant.get("authority") or "Evaluates solution; requires executive sign-off"

    if any(w in text.lower() for w in ("crm", "salesforce", "hubspot", "automate", "qualify", "pipeline", "manual", "leads", "sync", "workflow")):
        bant["need"] = bant.get("need") or text[:180].strip()

    timeline_match = re.search(r"(this week|this month|next week|next month|q[1-4]|within \d+ days|\d+ days|immediately|asap|next quarter)", text, re.IGNORECASE)
    if timeline_match:
        bant["timeline"] = timeline_match.group(1).strip()

    # Compute dynamic BANT lead score 0-100
    score = 15
    if bant.get("name"):
        score += 8
    if bant.get("company"):
        score += 10
    if bant.get("role"):
        score += 10
    if bant.get("email"):
        score += 10
    if bant.get("budget"):
        score += 15
    if bant.get("authority"):
        score += 10
    if bant.get("need"):
        score += 12
    if bant.get("timeline"):
        score += 10
    bant["lead_score"] = min(100, score)
    return bant


async def _detect_and_qualify_node(state: SalesAgentState) -> dict[str, Any]:
    """Extract language, sentiment, and English-normalized BANT on every turn and sync to CRM."""
    last_user_msg = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_msg = str(msg.content)
            break

    existing_bant = dict(state.get("bant") or {})
    detected_lang = _detect_language_heuristic(last_user_msg)
    bant = _extract_bant_heuristic(last_user_msg, existing_bant)
    sentiment = _classify_sentiment_heuristic(last_user_msg, int(bant.get("lead_score", 15)))

    llm = get_chat_model(temperature=0.0)
    if llm is not None and last_user_msg:
        history_snippet = "\n".join(
            f"{'Prospect' if isinstance(m, HumanMessage) else 'Ava'}: {m.content}"
            for m in state["messages"][-8:]
            if isinstance(m, (HumanMessage, AIMessage)) and m.content
        )
        try:
            resp = await llm.ainvoke(
                [
                    SystemMessage(content=BANT_EXTRACTOR_PROMPT),
                    HumanMessage(content=f"Existing BANT: {json.dumps(existing_bant)}\n\nConversation:\n{history_snippet}"),
                ]
            )
            raw = str(resp.content).strip()
            json_match = re.search(r"\{[\s\S]*\}", raw)
            if json_match:
                parsed = json.loads(json_match.group(0))
                if parsed.get("detected_language"):
                    detected_lang = parsed["detected_language"]
                if parsed.get("sentiment") in ("Positive", "Neutral", "Skeptical", "Frustrated", "Ready to Buy"):
                    sentiment = parsed["sentiment"]
                parsed_bant = parsed.get("bant") or {}
                for key in ("name", "email", "company", "role", "budget", "authority", "need", "timeline"):
                    if parsed_bant.get(key):
                        bant[key] = parsed_bant[key]
                if isinstance(parsed_bant.get("lead_score"), (int, float)):
                    bant["lead_score"] = max(0, min(100, int(parsed_bant["lead_score"])))
        except Exception:
            pass

    crm_result = upsert_crm_lead_data(
        bant=bant,
        sentiment=sentiment,
        detected_language=detected_lang,
        lead_id=state.get("lead_id"),
    )

    return {
        "detected_language": detected_lang,
        "sentiment": sentiment,
        "bant": bant,
        "lead_id": crm_result["lead_id"],
        "rag_sources": [],
        "tool_events": [],
    }


def _build_mock_reply(
    user_text: str,
    language: str,
    bant: dict[str, Any],
    sentiment: str,
) -> tuple[str, list[str], list[dict[str, Any]], Optional[dict[str, Any]]]:
    """Deterministic RAG-grounded, booking-capable fallback when no external LLM key is configured."""
    lower = user_text.lower()
    rag_sources: list[str] = []
    tool_events: list[dict[str, Any]] = []
    booked_appt: Optional[dict[str, Any]] = None

    # 1. Check if user is confirming a demo slot or asking to schedule
    slots = get_available_slots_data(days_ahead=3)
    open_slots = [s for s in slots if s["available"]]

    wants_booking = any(
        k in lower
        for k in ("book", "schedule", "demo", "calendar", "slot", "slot 1", "first", "confirm", "reunion", "agendar")
    )
    confirms_time = any(
        k in lower
        for k in ("9:30", "11:00", "2:00", "4:00", "book the first", "yes please", "confirm", "works for me", "let's book", "go ahead")
    )

    if confirms_time and open_slots:
        chosen = open_slots[0]
        for s in open_slots:
            if any(tok in lower for tok in ("9:30", "11:00", "2:00", "4:00")) and any(
                tok in s["slot_label"].lower() for tok in ("9:30", "11:00", "2:00", "4:00") if tok in lower
            ):
                chosen = s
                break

        tool_events.append({"tool": "check_available_slots", "summary": f"Found {len(open_slots)} open AE slots"})
        booking = book_appointment_data(
            slot_iso=chosen["slot_iso"],
            lead_name=bant.get("name") or "Alex Rivera",
            company=bant.get("company") or "Acme Cloud",
            email=bant.get("email") or "alex@acmecloud.io",
            notes=f"Need: {bant.get('need') or 'RevOps automation'} | Budget: {bant.get('budget') or 'TBD'}",
        )
        if booking.get("ok"):
            booked_appt = booking["appointment"]
            tool_events.append({"tool": "book_appointment", "summary": f"Confirmed {booked_appt['slot_label']}"})
            if language == "Spanish":
                reply = (
                    f"Perfecto, he confirmado tu demostracion para el {booked_appt['slot_label']} con {booked_appt['ae_owner']}. "
                    f"El enlace de la reunion es {booked_appt['meeting_link']} y ya actualizamos tu registro en nuestro CRM."
                )
            elif language == "Hindi":
                reply = (
                    f"Bahut badhiya! Maine aapka demo {booked_appt['slot_label']} ko {booked_appt['ae_owner']} ke saath confirm kar diya hai. "
                    f"Aapka meeting link {booked_appt['meeting_link']} hai aur CRM mein saari details update ho gayi hain."
                )
            else:
                reply = (
                    f"You're all set! I've booked your personalized NovaFlow AI demo for {booked_appt['slot_label']} with {booked_appt['ae_owner']}. "
                    f"Your meeting link is {booked_appt['meeting_link']}, and I've synced your qualification notes straight into our CRM."
                )
            return reply, rag_sources, tool_events, booked_appt

    if wants_booking and open_slots:
        tool_events.append({"tool": "check_available_slots", "summary": f"Checked {len(open_slots)} open AE slots"})
        slot_1 = open_slots[0]["slot_label"]
        slot_2 = open_slots[1]["slot_label"] if len(open_slots) > 1 else slot_1
        if language == "Spanish":
            reply = (
                f"Con mucho gusto agendamos una demo personalizada. Tenemos disponibilidad el {slot_1} o el {slot_2}. "
                f"Cual horario prefieres y a que correo te enviamos la invitacion?"
            )
        elif language == "Hindi":
            reply = (
                f"Bilkul, main aapka live demo abhi schedule kar sakti hoon. Hamare paas {slot_1} aur {slot_2} ke slots khali hain. "
                f"Kaunsa time aapko suit karega aur aapka email address kya hai?"
            )
        else:
            reply = (
                f"I'd love to get a tailored demo on the calendar for you. We have open slots on {slot_1} or {slot_2}. "
                f"Which time works best, and what email should I send the calendar invite to?"
            )
        return reply, rag_sources, tool_events, None

    # 2. Check RAG knowledge base for product / pricing / security / objection questions
    kb_triggers = (
        "price", "pricing", "cost", "plan", "tier", "expensive", "budget", "seat", "starter", "growth", "enterprise",
        "salesforce", "hubspot", "integrat", "snowflake", "soc", "security", "gdpr", "privacy", "gong", "feature",
        "implement", "long", "how much", "precio", "cuanto", "seguridad", "kitna", "daam", "suraksha",
    )
    if any(t in lower for t in kb_triggers):
        hits = query_knowledge_base(user_text, top_k=2)
        rag_sources = [f"{h['source']} ({h['section']})" for h in hits]
        tool_events.append({"tool": "search_knowledge_base", "summary": f"Retrieved {len(hits)} KB chunks: {', '.join(rag_sources)}"})

        if any(t in lower for t in ("expensive", "too much", "mahanga", "caro", "gong", "already use")):
            if language == "Spanish":
                reply = (
                    "Entiendo perfectamente la preocupacion por el presupuesto. Nuestro plan Growth cuesta 99 dolares por usuario al mes, "
                    "ahorra entre 6 y 8 horas semanales por vendedor y ofrecemos un piloto guiado de 14 dias sin tarifa de implementacion en contratos anuales. "
                    "Cuantos representantes tiene tu equipo actualmente?"
                )
            elif language == "Hindi":
                reply = (
                    "Main aapki budget chinta samajhti hoon. Hamara Growth plan 99 dollars per seat per month hai, jo har sales rep ke 6 se 8 ghante bachata hai aur 45 din mein ROI deta hai. "
                    "Hum 14-day guided pilot bhi dete hain aur annual plan par 2,500 dollar ki onboarding fee maaf hai. Aapki team mein kitne reps hain?"
                )
            else:
                reply = (
                    "I completely understand watching software spend closely. Our Growth plan is $99 per user per month, and teams typically save 6 to 8 hours per rep each week while seeing an 18 to 24 percent lift in qualified pipeline—paying back in under 45 days. "
                    "We also offer a 14-day guided pilot and waive the $2,500 onboarding fee on annual plans. Roughly how many reps are on your team?"
                )
            return reply, rag_sources, tool_events, None

        if any(t in lower for t in ("soc", "security", "gdpr", "privacy", "hipaa", "seguridad", "suraksha")):
            if language == "Hindi":
                reply = (
                    "Security hamari top priority hai—NovaFlow AI SOC 2 Type II certified aur GDPR compliant hai, AES-256 encryption aur automatic PII redaction ke saath. "
                    "Hum kabhi bhi aapke call data par public AI models train nahi karte. Kya aap is quarter mein rollout plan kar rahe hain?"
                )
            elif language == "Spanish":
                reply = (
                    "NovaFlow AI cuenta con certificacion SOC 2 Type II y cumplimiento GDPR, cifrado AES-256 y redaccion automatica de datos PII. "
                    "Nunca entrenamos modelos publicos con los datos de nuestros clientes. Para que fecha buscan implementar?"
                )
            else:
                reply = (
                    "Great question—NovaFlow AI is SOC 2 Type II certified and GDPR compliant, with AES-256 encryption at rest, automatic PII redaction, and zero customer data used to train public models. "
                    "We can share our full security packet during a quick technical walkthrough. What timeline are you targeting for rollout?"
                )
            return reply, rag_sources, tool_events, None

        # General pricing / features RAG response
        if language == "Spanish":
            reply = (
                "Tenemos tres planes: Starter a 49 dolares por usuario al mes, Growth a 99 dolares con integracion bidireccional con Salesforce, HubSpot y Slack, y Enterprise con SSO y Snowflake. "
                "Que CRM utilizan hoy y para cuando buscan lanzar?"
            )
        elif language == "Hindi":
            reply = (
                "Hamare teen plans hain: Starter 49 dollars per user, Growth 99 dollars jisme Salesforce, HubSpot aur Slack ki live sync milti hai, aur Enterprise custom pricing par. "
                "Aap abhi kaunsa CRM use kar rahe hain aur kab tak live jana chahte hain?"
            )
        else:
            reply = (
                "We offer three clear tiers: Starter at $49 per user per month, Growth at $99 per user with bi-directional Salesforce, HubSpot, Slack, and real-time BANT scoring, and Enterprise with Okta SSO and Snowflake sync. "
                "Go-live typically takes under 10 business days. Which CRM is your team running today?"
            )
        return reply, rag_sources, tool_events, None

    # 3. Conversational discovery reply tailored to missing BANT fields
    missing_prompts = []
    if not bant.get("need"):
        missing_prompts.append("what manual bottlenecks your sales or RevOps team is trying to solve")
    elif not bant.get("budget"):
        missing_prompts.append("how many seats you're looking to equip or what budget range you have in mind")
    elif not bant.get("timeline"):
        missing_prompts.append("what timeline you're aiming for to go live")
    else:
        missing_prompts.append("if you'd like me to check open demo times for a live walkthrough")

    if language == "Spanish":
        reply = (
            f"Gracias por compartir eso{', ' + bant['name'] if bant.get('name') else ''}. "
            "En NovaFlow AI ayudamos a equipos B2B a calificar leads y actualizar su CRM automaticamente en tiempo real. "
            "Para orientarte mejor, que CRM usan actualmente y cual es su principal prioridad este trimestre?"
        )
    elif language == "Hindi":
        reply = (
            f"Shukriya{', ' + bant['name'] if bant.get('name') else ''}! NovaFlow AI aapki sales team ke calls qualify karke CRM automatically update karta hai. "
            "Aapko sahi plan batane ke liye, aapki team mein kitne sales reps hain aur aapka target timeline kya hai?"
        )
    else:
        reply = (
            f"Thanks for sharing that{', ' + bant['name'] if bant.get('name') else ''}! "
            f"NovaFlow AI automates live lead qualification and bi-directional CRM updates so reps spend more time closing. "
            f"To tailor this for {bant.get('company') or 'your team'}, could you share {missing_prompts[0]}?"
        )
    return reply, rag_sources, tool_events, None


async def _agent_reason_node(state: SalesAgentState) -> dict[str, Any]:
    """Run tool-augmented LLM reasoning, or deterministic RAG+booking fallback if in mock mode."""
    llm = get_chat_model(temperature=0.25)
    last_user_msg = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_msg = str(msg.content)
            break

    if llm is None:
        reply, rag_sources, tool_events, booked_appt = _build_mock_reply(
            user_text=last_user_msg,
            language=state["detected_language"],
            bant=state["bant"],
            sentiment=state["sentiment"],
        )
        return {
            "messages": [AIMessage(content=reply)],
            "assistant_reply": reply,
            "rag_sources": rag_sources,
            "tool_events": tool_events,
            "booked_appointment": booked_appt or state.get("booked_appointment"),
        }

    # Real LLM with tool calling loop
    llm_with_tools = llm.bind_tools(AGENT_TOOLS)
    context_note = (
        f"Current state -> Mode: {state['mode']} | Detected Language: {state['detected_language']} | "
        f"Sentiment: {state['sentiment']} | BANT: {json.dumps(state['bant'])}"
    )
    prompt_messages = [
        SystemMessage(content=f"{SYSTEM_PROMPT}\n\n{context_note}"),
        *state["messages"][-14:],
    ]

    rag_sources: list[str] = list(state.get("rag_sources") or [])
    tool_events: list[dict[str, Any]] = list(state.get("tool_events") or [])
    booked_appt = state.get("booked_appointment")
    new_messages: list[Any] = []

    tool_map = {t.name: t for t in AGENT_TOOLS}
    for _ in range(4):
        ai_msg = await llm_with_tools.ainvoke(prompt_messages)
        new_messages.append(ai_msg)
        prompt_messages.append(ai_msg)

        if not getattr(ai_msg, "tool_calls", None):
            reply = str(ai_msg.content).strip()
            return {
                "messages": new_messages,
                "assistant_reply": reply,
                "rag_sources": rag_sources,
                "tool_events": tool_events,
                "booked_appointment": booked_appt,
            }

        for tc in ai_msg.tool_calls:
            name = tc["name"]
            args = tc.get("args") or {}
            tool_fn = tool_map.get(name)
            if tool_fn is None:
                result = {"error": f"Unknown tool {name}"}
            else:
                result = tool_fn.invoke(args)

            if name == "search_knowledge_base":
                rag_sources.append(f"KB query: {args.get('query', '')[:40]}")
                tool_events.append({"tool": name, "summary": f"Queried '{args.get('query', '')[:45]}'"})
            elif name == "check_available_slots":
                count = len(result) if isinstance(result, list) else 0
                tool_events.append({"tool": name, "summary": f"Checked {count} open demo slots"})
            elif name == "book_appointment":
                if isinstance(result, dict) and result.get("ok"):
                    booked_appt = result["appointment"]
                    tool_events.append({"tool": name, "summary": f"Confirmed {booked_appt['slot_label']}"})
                else:
                    tool_events.append({"tool": name, "summary": f"Booking attempt: {result}"})
            elif name == "upsert_crm_lead":
                tool_events.append({"tool": name, "summary": "Synced BANT fields to CRM"})

            tm = ToolMessage(content=json.dumps(result, default=str), tool_call_id=tc["id"])
            new_messages.append(tm)
            prompt_messages.append(tm)

    fallback_reply = "I've updated your details in our system. Could you confirm which demo slot works best for your team?"
    return {
        "messages": new_messages,
        "assistant_reply": fallback_reply,
        "rag_sources": rag_sources,
        "tool_events": tool_events,
        "booked_appointment": booked_appt,
    }


def build_sales_graph():
    """Compile the stateful LangGraph workflow with persistent in-memory checkpoints."""
    graph = StateGraph(SalesAgentState)
    graph.add_node("detect_and_qualify", _detect_and_qualify_node)
    graph.add_node("agent_reason", _agent_reason_node)

    graph.add_edge(START, "detect_and_qualify")
    graph.add_edge("detect_and_qualify", "agent_reason")
    graph.add_edge("agent_reason", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


sales_agent_graph = build_sales_graph()
