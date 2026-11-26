"""Modular STT and TTS provider adapters with automatic browser fallbacks."""

import base64
from typing import Any, Optional
import httpx

from app.config import settings


class VoicePipelineService:
    """Abstraction layer for Deepgram STT and OpenAI / ElevenLabs TTS with safe fallbacks."""

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/webm",
        language_hint: Optional[str] = None,
    ) -> dict[str, Any]:
        """Transcribe uploaded audio bytes via Deepgram, or signal browser fallback."""
        provider = settings.resolved_stt_provider()
        if provider != "deepgram" or not audio_bytes:
            return {"provider": "browser", "text": "", "language": language_hint or "English", "fallback": True}

        params: dict[str, str] = {
            "model": "nova-2",
            "smart_format": "true",
            "detect_language": "true",
        }
        headers = {
            "Authorization": f"Token {settings.deepgram_api_key}",
            "Content-Type": mime_type,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.deepgram.com/v1/listen",
                    params=params,
                    headers=headers,
                    content=audio_bytes,
                )
                resp.raise_for_status()
                payload = resp.json()
            channel = payload["results"]["channels"][0]
            alt = channel["alternatives"][0]
            detected = channel.get("detected_language", "en")
            lang_map = {"en": "English", "es": "Spanish", "hi": "Hindi", "fr": "French", "de": "German"}
            return {
                "provider": "deepgram",
                "text": alt.get("transcript", "").strip(),
                "language": lang_map.get(detected[:2], language_hint or "English"),
                "fallback": False,
            }
        except Exception as exc:
            return {
                "provider": "browser",
                "text": "",
                "language": language_hint or "English",
                "fallback": True,
                "error": str(exc),
            }

    async def synthesize_speech(self, text: str) -> dict[str, Any]:
        """Synthesize assistant text to base64 audio using OpenAI/ElevenLabs, or browser fallback."""
        provider = settings.resolved_tts_provider()
        if provider == "browser" or not text.strip():
            return {"provider": "browser", "audio_base64": None, "audio_mime": None}

        if provider == "openai":
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/audio/speech",
                        headers={
                            "Authorization": f"Bearer {settings.openai_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "tts-1",
                            "voice": settings.openai_tts_voice,
                            "input": text[:1500],
                            "response_format": "mp3",
                        },
                    )
                    resp.raise_for_status()
                    encoded = base64.b64encode(resp.content).decode("ascii")
                    return {"provider": "openai", "audio_base64": encoded, "audio_mime": "audio/mpeg"}
            except Exception:
                return {"provider": "browser", "audio_base64": None, "audio_mime": None}

        if provider == "elevenlabs":
            try:
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(
                        url,
                        headers={
                            "xi-api-key": settings.elevenlabs_api_key,
                            "Content-Type": "application/json",
                        },
                        json={
                            "text": text[:1500],
                            "model_id": "eleven_multilingual_v2",
                            "voice_settings": {"stability": 0.45, "similarity_boost": 0.75},
                        },
                    )
                    resp.raise_for_status()
                    encoded = base64.b64encode(resp.content).decode("ascii")
                    return {"provider": "elevenlabs", "audio_base64": encoded, "audio_mime": "audio/mpeg"}
            except Exception:
                return {"provider": "browser", "audio_base64": None, "audio_mime": None}

        return {"provider": "browser", "audio_base64": None, "audio_mime": None}


voice_service = VoicePipelineService()
