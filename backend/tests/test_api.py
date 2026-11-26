"""End-to-end backend verification tests covering seeding, RAG, LangGraph, booking, insights, and WS."""

from fastapi.testclient import TestClient

from app.main import app


def test_full_sales_call_flow() -> None:
    with TestClient(app) as client:
        # 1. Health & pre-seeded data
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["kb_chunks"] >= 5

        leads_before = client.get("/api/leads")
        assert leads_before.status_code == 200
        assert len(leads_before.json()) >= 3

        slots = client.get("/api/appointments/slots")
        assert slots.status_code == 200
        assert any(s["available"] for s in slots.json())

        # 2. Start inbound call
        start_res = client.post(
            "/api/calls/start",
            json={"mode": "inbound", "prospect_name": "Priya Nair", "company": "CloudGrid"},
        )
        assert start_res.status_code == 200
        session_id = start_res.json()["session_id"]

        # 3. Turn 1: Pricing & Salesforce RAG + BANT extraction
        turn1 = client.post(
            f"/api/calls/{session_id}/turn",
            json={
                "text": (
                    "We have 30 sales reps at CloudGrid struggling with manual Salesforce updates. "
                    "I'm the VP of RevOps with a $35,000 budget to launch next month. How much does Growth cost?"
                )
            },
        )
        assert turn1.status_code == 200
        data1 = turn1.json()
        assert data1["bant"]["company"] == "CloudGrid"
        assert data1["bant"]["lead_score"] >= 60
        assert len(data1["rag_sources"]) >= 1

        # 4. Turn 2: Ask for demo slots
        turn2 = client.post(
            f"/api/calls/{session_id}/turn",
            json={"text": "That sounds great, can we book a live demo? My email is priya@cloudgrid.io"},
        )
        assert turn2.status_code == 200
        assert turn2.json()["bant"]["email"] == "priya@cloudgrid.io"

        # 5. Turn 3: Confirm first slot -> autonomous booking
        turn3 = client.post(
            f"/api/calls/{session_id}/turn",
            json={"text": "Yes please, book the first slot for me!"},
        )
        assert turn3.status_code == 200
        data3 = turn3.json()
        assert data3["booked_appointment"] is not None
        assert data3["booked_appointment"]["status"] == "Confirmed"

        # 6. End call -> post-call insights
        end_res = client.post(f"/api/calls/{session_id}/end?wait=true")
        assert end_res.status_code == 200
        insight = end_res.json()["insight"]
        assert insight["conversion_probability"] >= 70
        assert "CloudGrid" in insight["executive_summary"]

        # 7. Analytics endpoint reflects updated counts
        analytics = client.get("/api/analytics")
        assert analytics.status_code == 200
        assert analytics.json()["booked_demos"] >= 3


def test_multilingual_and_websocket_barge_in() -> None:
    with TestClient(app) as client:
        start_res = client.post("/api/calls/start", json={"mode": "outbound"})
        session_id = start_res.json()["session_id"]

        with client.websocket_connect(f"/ws/call/{session_id}") as ws:
            connected = ws.receive_json()
            assert connected["type"] == "connected"

            ws.send_json({"type": "user_text", "text": "Hola, somos 20 personas y queremos saber el precio del plan Growth."})
            reply = ws.receive_json()
            assert reply["type"] == "agent_turn"
            assert reply["data"]["detected_language"] == "Spanish"

            ws.send_json({"type": "barge_in"})
            interrupted = ws.receive_json()
            assert interrupted["type"] == "interrupted"

            ws.send_json({"type": "end_call"})
            done = ws.receive_json()
            assert done["type"] == "insights_ready"
            assert done["data"]["detected_language"] == "Spanish"
