# NovaFlow AI — Autonomous AI Sales Voice Agent (MVP)

A production-structured, full-stack MVP of an **Autonomous AI Sales Voice Agent** built for live technical evaluations and live-coding interviews. It handles inbound/outbound B2B SaaS calls, performs real-time RAG retrieval, extracts English-normalized BANT qualification & sentiment, speaks in the prospect's language, handles live barge-in interruptions, books demo appointments into SQLite CRM, and generates asynchronous post-call executive insights.

---

## Core Capabilities

- **Real-Time Voice & Text Interaction:** Live WebSocket streaming (`/ws/call/{session_id}`), mic capture via Web Speech API (or Deepgram Nova-2), spoken TTS replies (OpenAI TTS / ElevenLabs / browser `speechSynthesis` fallback), instant **barge-in interruption**, and a **text-input fallback toggle** for silent testing.
- **LangGraph Stateful Agent:** Multi-turn checkpointed conversation state (`MemorySaver`), automatic language detection (English, Spanish, Hindi, French) with English-normalized CRM syncing.
- **ChromaDB RAG Knowledge Base:** Pre-seeded B2B SaaS documentation (`pricing.md`, `product_features.md`, `objection_handling.md`) with offline-safe local hashing embeddings (or OpenAI embeddings).
- **Live BANT & Sentiment Inspector:** Updates `name`, `company`, `role`, `budget`, `authority`, `need`, `timeline`, `lead_score` (0–100), and `sentiment` on every conversational turn.
- **Autonomous Calendar Booking & CRM:** Agent calls `check_available_slots()` and `book_appointment()` to reserve open AE slots and update lead status in SQLite (`leads`, `appointments`, `call_sessions`, `call_insights`).
- **Post-Call Insights Pipeline:** Clicking **End Call** triggers executive summary, key objections, next best action, and conversion probability analytics.

---

## 1-Command Setup & Run

> **Zero-Key Demo Mode:** The app works out of the box **without any API keys** (using local ChromaDB embeddings, deterministic RAG/BANT fallback orchestration, and browser Web Speech API/speechSynthesis). Add real keys to `.env` anytime to switch to OpenAI / Groq / Gemini + Deepgram + ElevenLabs.

### Step 1: Configure Environment
```bash
cp .env.example .env
# Optional: Add OPENAI_API_KEY / GROQ_API_KEY / GEMINI_API_KEY / DEEPGRAM_API_KEY in .env
```

### Step 2: Launch Backend & Frontend

**Terminal 1 — Backend (FastAPI + LangGraph + ChromaDB + SQLite):**
```bash
cd backend
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
# (Add --reload during live coding if your machine has >= 2 GB free virtual memory)
```

**Terminal 2 — Frontend (React + Vite + Tailwind):**
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in Chrome or Edge.

---

## Live Evaluation Demo Script (3–4 Minutes)

Use either your **microphone** (click `Enable Mic`) or the **1-click Demo Turn pills** in the Call Console:

1. **Start Inbound Call:** Click **Start Inbound Call**. Ava greets you and begins speaking.
2. **Barge-In / Interruption:** While Ava is speaking, click **Barge-In** (or start typing / speaking) to verify instant audio cancellation and WebSocket `interrupted` signaling.
3. **BANT Qualification + RAG Pricing:** Send:
   > *"Hi, I'm David Chen, VP of RevOps at OrbitScale. We have 35 AEs wasting hours updating Salesforce and a $40,000 budget to fix this next month. How much does Growth cost?"*
   - Observe the **Live BANT Inspector** populate `David Chen`, `OrbitScale`, `VP of RevOps`, `$40,000`, `next month`, and bump `lead_score`.
   - Observe the **LangGraph Tool Trace** retrieve `pricing.md` & `product_features.md` from ChromaDB.
4. **Objection Handling (SOC 2):** Send:
   > *"Our InfoSec team is strict about SOC 2 compliance and AI data privacy. How do you handle that?"*
   - Ava cites SOC 2 Type II, AES-256 encryption, automatic PII redaction, and zero public model training.
5. **Multilingual Test (Spanish or Hindi):** Send:
   > *"Hola, somos 25 personas en nuestro equipo de ventas y queremos ver precios y una demo."*
   - Ava responds fluently in Spanish while keeping CRM fields normalized in English.
6. **Autonomous Demo Booking:** Send:
   > *"That sounds great. Can we schedule a live demo? My email is david.chen@orbitscale.io"* -> then confirm *"Yes please, book the first open slot for me!"*
   - Watch `book_appointment` confirm the slot, generate a meeting link, and update **CRM & Calendar** tab to `Demo Booked`.
7. **End Call -> Post-Call Insights:** Click **End Call**, then open the **Post-Call Insights** tab to view the executive summary, objections, next best action, and conversion probability.

---

## Documentation

- [System Architecture & Sequence Diagrams](docs/ARCHITECTURE.md)
- [100k Scalability, Security & Unit-Economics Defense Guide](docs/SCALABILITY_AND_DEFENSE.md)
