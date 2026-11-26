# System Architecture — NovaFlow AI Autonomous Sales Voice Agent

This document describes the end-to-end architecture, LangGraph state orchestration, and real-time voice/barge-in data flow for the **Autonomous AI Sales Voice Agent** MVP.

---

## 1. High-Level System Architecture

```mermaid
flowchart TD
    User["Prospect Browser / Mic & Speaker"] <-->|"WebRTC / Web Speech API + Media"| UI["React + Vite + Tailwind UI"]
    UI <-->|"WebSocket /ws/call/session_id + REST /api/*"| API["FastAPI Backend (ASGI)"]

    subgraph VoicePipeline["Voice Pipeline (app/voice/stt_tts.py)"]
        STT["STT Adapter (Deepgram Nova-2 / Browser Fallback)"]
        TTS["TTS Adapter (OpenAI TTS / ElevenLabs / Browser Fallback)"]
    end

    API <--> STT
    API <--> TTS

    subgraph Orchestration["LangGraph Stateful Agent (app/agent/graph.py)"]
        N1["Node 1: detect_and_qualify (Language + Sentiment + BANT)"]
        N2["Node 2: agent_reason (Tool-Calling Sales LLM / Fallback)"]
        CP["MemorySaver Checkpointer (thread_id = session_id)"]
        N1 --> N2
        N1 -.-> CP
        N2 -.-> CP
    end

    API --> Orchestration

    subgraph Tools["Agent Tools (app/agent/tools.py)"]
        T1["search_knowledge_base"]
        T2["check_available_slots"]
        T3["book_appointment"]
        T4["upsert_crm_lead"]
    end

    N2 <--> Tools

    T1 <-->|"Semantic Top-K"| Chroma["ChromaDB Persistent Vector Store"]
    T2 <--> SQLite["SQLite CRM DB (leads, appointments, call_sessions, call_insights)"]
    T3 <--> SQLite
    T4 <--> SQLite
    N1 -->|"Turn-by-Turn CRM Sync"| T4

    API -->|"Async Background Task on End Call"| PostCall["Post-Call Insights Service (app/services/post_call.py)"]
    PostCall --> SQLite
```

---

## 2. LangGraph Multi-Turn State Flow

On every prospect utterance, the graph executes two deterministic stages backed by a session-scoped `MemorySaver` checkpoint (`thread_id = session_id`):

```mermaid
flowchart LR
    S(["START"]) --> DQ["detect_and_qualify: Detect Language, Classify Sentiment, Extract English BANT, Compute Score 0-100, Upsert CRM Lead"]
    DQ --> AR["agent_reason: Bind Tools & System Prompt, Enforce Same-Language Reply"]
    AR -->|"Tool Calls Needed"| TC["Execute Tools: search_knowledge_base / check_available_slots / book_appointment"]
    TC --> AR
    AR -->|"Final Spoken Reply"| E(["END"])
```

### Key Architectural Invariants
1. **Multilingual Input, Normalized CRM Output:** Regardless of whether the prospect speaks English, Spanish, or Hindi, `detect_and_qualify` instructs the extractor to normalize BANT fields (`budget`, `authority`, `need`, `timeline`) to English before persisting to SQLite, while `agent_reason` replies fluently in `detected_language`.
2. **RAG-Grounded Responses:** Pricing tiers, Salesforce/HubSpot integration specs, SOC 2 security answers, and objection rebuttals are retrieved from ChromaDB (`pricing.md`, `product_features.md`, `objection_handling.md`) before generating an answer.
3. **Graceful Zero-Key Resilience:** If external API keys (`OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY`) are absent or fail during a live evaluation, every layer degrades gracefully to local embeddings, deterministic NLP/RAG orchestration, and browser Web Speech API / `speechSynthesis`.

---

## 3. End-to-End Voice Call & Barge-In Sequence

```mermaid
sequenceDiagram
    autonumber
    actor P as Prospect
    participant FE as React Call Console
    participant WS as FastAPI WebSocket
    participant LG as LangGraph Agent
    participant DB as ChromaDB & SQLite
    participant PC as Post-Call Service

    P->>FE: Click "Start Inbound Call"
    FE->>WS: POST /api/calls/start + Open WS /ws/call/{id}
    WS-->>FE: Greeting + Initial BANT State
    FE-->>P: Speak Greeting (TTS / speechSynthesis)

    P->>FE: Speaks question (or uses Text Fallback)
    FE->>WS: {"type": "user_text", "text": "..."}
    WS->>LG: ainvoke(session_id)
    LG->>DB: Upsert BANT + Sentiment + Lead Score
    LG->>DB: search_knowledge_base("Growth pricing")
    DB-->>LG: Retrieved pricing & ROI chunks
    LG-->>WS: Spoken reply + BANT + Tool Trace
    WS-->>FE: {"type": "agent_turn", "data": ...}
    FE-->>P: Play TTS Audio

    Note over P,FE: Prospect interrupts mid-sentence (Barge-In)
    P->>FE: Starts speaking / clicks Barge-In
    FE->>FE: Immediately cancel speechSynthesis / Audio playback
    FE->>WS: {"type": "barge_in"}
    WS->>LG: Cancel active asyncio.Task
    WS-->>FE: {"type": "interrupted"}

    P->>FE: Confirms demo slot
    FE->>WS: {"type": "user_text", "text": "Book the first slot"}
    WS->>LG: book_appointment(slot_iso, lead_name, company, email)
    LG->>DB: Insert Appointment + Mark Lead "Demo Booked"
    LG-->>FE: Confirmation + Meeting Link

    P->>FE: Click "End Call"
    FE->>WS: POST /api/calls/{id}/end
    WS->>PC: Generate Executive Summary, Objections, Next Best Action
    PC->>DB: Persist CallInsight
    PC-->>FE: Return CallInsight + Refresh Analytics
```
