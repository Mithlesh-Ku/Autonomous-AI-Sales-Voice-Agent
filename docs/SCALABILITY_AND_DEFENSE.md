# Scalability, Security & Unit-Economics Defense Guide

This guide prepares you for senior systems-architecture Q&A during a live technical evaluation—covering how this MVP scales from a single-node prototype to **100,000+ active/concurrent voice sessions**.

---

## 1. Scaling Real-Time Voice Transport to 100k Users (WebSockets -> WebRTC / LiveKit)

### Why Raw WebSockets Break at High Concurrency & Jitter
In this MVP, audio/transcript frames travel over TCP-backed WebSockets (`FastAPI` + browser `SpeechRecognition`). At production telephony scale:
- **Head-of-Line (HoL) Blocking:** TCP retransmits lost packets, introducing 300–800ms audio stalls on lossy mobile networks.
- **Turn Detection & Echo Cancellation:** Barge-in requires sub-150ms Voice Activity Detection (VAD) and Acoustic Echo Cancellation (AEC) so the agent does not interrupt itself.

### Production Migration Path
1. **Media Plane via LiveKit (WebRTC SFU + SIP Bridge):**
   - Replace browser-to-FastAPI audio streaming with **LiveKit Cloud / Self-Hosted LiveKit SFU** over UDP/SRTP.
   - Connect PSTN phone numbers (inbound/outbound cold calls) via **Twilio / Telnyx SIP Trunks** directly into LiveKit Rooms.
   - Run **Silero VAD + Semantic End-of-Turn detection** inside lightweight **LiveKit Agent Workers** close to the media edge, dropping barge-in latency from ~400ms to **<120ms**.
2. **Streaming Pipeline Parallelism:**
   - Stream Deepgram Nova-2 over persistent WebSocket -> stream LLM tokens -> sentence-chunk into ElevenLabs Flash v2.5 / Cartesia Sonic WebSocket TTS so Time-To-First-Audio (TTFA) stays under **450–650ms**.

---

## 2. Stateless Compute, Distributed State & Database Tiering

| Layer | MVP Prototype | 100k-Scale Production |
| :--- | :--- | :--- |
| **API / Agent Workers** | Single `uvicorn` FastAPI process | Stateless Kubernetes pods behind Envoy / AWS ALB with HPA on active room count & CPU |
| **LangGraph Checkpoints** | In-process `MemorySaver` | `AsyncPostgresSaver` + **Redis Cluster** hot-state cache (sub-2ms turn reads, zero sticky-session requirement) |
| **Relational CRM DB** | Local SQLite (`sales_agent.db`) | **Managed PostgreSQL** (RDS Aurora / Cloud SQL) + **PgBouncer** connection pooling + read replicas for analytics |
| **Vector Knowledge Base** | Local ChromaDB (`./data/chroma_db`) | **`pgvector` (HNSW)** or **Qdrant / Pinecone** with per-tenant `org_id` metadata filters and Redis semantic query caching |
| **Post-Call Pipelines** | FastAPI `BackgroundTasks` | Durable task queue (**Celery / Temporal / BullMQ on Redis**) with dead-letter retries and webhook delivery to Salesforce/HubSpot |

### Horizontal Scaling Math for 100,000 Users
- Assuming 100,000 active B2B seats with **5% peak concurrency = 5,000 simultaneous live calls**:
  - **Voice/Agent Workers:** Each async Python worker handles ~50 concurrent streaming sessions -> **~100 stateless worker pods** (4 vCPU, 8 GB RAM each).
  - **Redis State:** ~50 KB checkpoint + transcript buffer per active call -> ~250 MB active RAM footprint (easily fits on a single replicated Redis cluster).
  - **PostgreSQL Writes:** 1 CRM upsert every ~8 seconds per active call -> ~625 writes/sec, well within a single primary + PgBouncer.

---

## 3. Security, Privacy & Enterprise Guardrails

1. **Automated PII Redaction Pipeline:**
   - Before transcripts hit LLM logs, vector stores, or analytics tables, run a streaming **Microsoft Presidio / regex NER scrubber** masking SSNs, payment card PANs, API tokens, and personal phone numbers with reversible vault tokens if CRM sync requires them.
2. **Encryption & Isolation:**
   - **In Transit:** TLS 1.3 for signaling/REST and DTLS-SRTP for WebRTC media.
   - **At Rest:** AES-256 encryption on PostgreSQL, S3 call recordings, and Redis; Enterprise tenants get **Customer-Managed Keys (CMK)** and regional data residency (`us-east` vs `eu-central` for GDPR).
3. **LLM & Tool-Call Guardrails:**
   - Strict **Pydantic schema validation** on every tool call (`book_appointment` validates slot ownership and rate-limits bookings per session).
   - **Zero-Data-Retention (ZDR) LLM Agreements:** Enterprise OpenAI/Anthropic/Groq endpoints ensure customer call audio/transcripts are never used for model training.
   - **Prompt Injection Defense:** System prompts strictly separate untrusted prospect speech (`HumanMessage`) from RAG tool results and prevent arbitrary pricing overrides (e.g., agent cannot invent unauthorized 90% discounts).

---

## 4. Unit-Economics Cost Breakdown (Per Call Minute)

Estimated production cost for a **1-minute live B2B voice conversation** (assuming ~150 spoken prospect words + ~150 spoken agent words per minute):

| Component | Provider / Configuration | Unit Rate | Est. Cost / Min |
| :--- | :--- | :--- | :--- |
| **Streaming STT** | Deepgram Nova-2 (Pay-as-you-go) | \$0.0043 / min | \$0.0043 |
| **LLM Inference** | GPT-4o-mini or Groq Llama-3.3-70B (~1.5k input + 300 output tokens/min across 3 turns) | ~\$0.15/1M in, \$0.60/1M out | \$0.0005 |
| **BANT + Sentiment Extraction** | Lightweight JSON pass (or bundled into single structured turn) | ~800 tokens/min | \$0.0003 |
| **Streaming TTS** | OpenAI `tts-1` (\$15/1M chars) or Cartesia Sonic (~900 chars/min) | ~\$0.0135 / 900 chars | \$0.0135 *(or \$0.045–\$0.09 with ElevenLabs)* |
| **WebRTC / SIP Telephony** | LiveKit Cloud + Twilio SIP | ~\$0.008–\$0.012 / min | \$0.0100 |
| **Infra & DB Overhead** | Compute + Redis + Postgres amortized | ~\$0.002 / min | \$0.0020 |
| **Total Blended COGS** | **Standard Low-Latency Stack** | — | **~\$0.031 / minute** *(~\$0.15 per 5-min qualified call)* |

### Cost-Optimization Levers at Scale
1. **Prompt Caching & Semantic FAQ Cache:** Cache system prompt + top RAG pricing chunks in Redis / provider prompt cache -> cuts LLM input token spend by **40–60%**.
2. **TTS Tiering:** Use Cartesia Sonic / OpenAI `tts-1` (\$0.013/min) for high-volume outbound qualification and reserve ElevenLabs custom voice clones (\$0.05–\$0.09/min) for inbound Enterprise accounts.
3. **End-of-Call Batching:** Run `post_call.py` summarization once on call hang-up rather than polling summaries every turn.
4. **Gross Margin Story:** At a Growth SaaS price of **\$99/seat/month** (or \$0.15–\$0.25/min usage add-on), a \$0.031/min COGS yields **~75%–85% gross margin**.
