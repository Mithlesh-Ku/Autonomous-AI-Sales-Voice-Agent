"""LangGraph state schema for multi-turn autonomous sales conversations."""

from typing import Annotated, Any, Optional, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class SalesAgentState(TypedDict):
    """Persistent conversation state stored in LangGraph checkpoints."""

    session_id: str
    mode: str  # "inbound" | "outbound"
    lead_id: Optional[int]
    messages: Annotated[list[BaseMessage], add_messages]
    detected_language: str
    sentiment: str
    bant: dict[str, Any]
    rag_sources: list[str]
    tool_events: list[dict[str, Any]]
    booked_appointment: Optional[dict[str, Any]]
    assistant_reply: str
