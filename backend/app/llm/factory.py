"""Configurable LangChain chat model factory for OpenAI, Groq, Gemini, or offline mock."""

from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings


def get_chat_model(temperature: float = 0.3) -> Optional[BaseChatModel]:
    """Instantiate the configured chat model, or return None for deterministic mock mode."""
    provider = settings.resolved_llm_provider()

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=temperature,
        )

    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            temperature=temperature,
        )

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=temperature,
        )

    return None
