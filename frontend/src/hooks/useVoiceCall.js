import { useCallback, useEffect, useRef, useState } from "react";
import { api, buildWsUrl } from "../api/client";

const LANG_TO_BCP47 = {
  English: "en-US",
  Spanish: "es-ES",
  Hindi: "hi-IN",
  French: "fr-FR",
  German: "de-DE",
  Portuguese: "pt-BR",
};

export function useVoiceCall({ onCrmUpdated, onInsightsReady }) {
  const [sessionId, setSessionId] = useState(null);
  const [callStatus, setCallStatus] = useState("idle"); // idle | connecting | active | thinking | ended
  const [mode, setMode] = useState("inbound");
  const [transcript, setTranscript] = useState([]);
  const [interimText, setInterimText] = useState("");
  const [bant, setBant] = useState({ lead_score: 15 });
  const [sentiment, setSentiment] = useState("Neutral");
  const [detectedLanguage, setDetectedLanguage] = useState("English");
  const [toolEvents, setToolEvents] = useState([]);
  const [ragSources, setRagSources] = useState([]);
  const [bookedAppointment, setBookedAppointment] = useState(null);
  const [latestInsight, setLatestInsight] = useState(null);
  const [isMicOn, setIsMicOn] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [bargeInCount, setBargeInCount] = useState(0);
  const [error, setError] = useState("");

  const wsRef = useRef(null);
  const audioRef = useRef(null);
  const recognitionRef = useRef(null);
  const isSpeakingRef = useRef(false);
  const callStatusRef = useRef("idle");

  useEffect(() => {
    isSpeakingRef.current = isSpeaking;
  }, [isSpeaking]);

  useEffect(() => {
    callStatusRef.current = callStatus;
  }, [callStatus]);

  const stopPlayback = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setIsSpeaking(false);
  }, []);

  const triggerBargeIn = useCallback(() => {
    if (isSpeakingRef.current || callStatusRef.current === "thinking") {
      stopPlayback();
      setBargeInCount((c) => c + 1);
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "barge_in" }));
      }
      setCallStatus("active");
    }
  }, [stopPlayback]);

  const speakResponse = useCallback(
    (text, language, audioBase64, audioMime) => {
      stopPlayback();
      if (!text) return;

      if (audioBase64 && audioMime) {
        const audio = new Audio(`data:${audioMime};base64,${audioBase64}`);
        audioRef.current = audio;
        setIsSpeaking(true);
        audio.onended = () => setIsSpeaking(false);
        audio.onerror = () => setIsSpeaking(false);
        audio.play().catch(() => setIsSpeaking(false));
        return;
      }

      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = LANG_TO_BCP47[language] || "en-US";
        utterance.rate = 1.03;
        setIsSpeaking(true);
        utterance.onend = () => setIsSpeaking(false);
        utterance.onerror = () => setIsSpeaking(false);
        window.speechSynthesis.speak(utterance);
      }
    },
    [stopPlayback]
  );

  const handleAgentPayload = useCallback(
    (data) => {
      setCallStatus("active");
      setDetectedLanguage(data.detected_language || "English");
      setSentiment(data.sentiment || "Neutral");
      if (data.bant) setBant(data.bant);
      if (data.tool_events?.length) {
        setToolEvents((prev) => [...data.tool_events, ...prev].slice(0, 16));
      }
      if (data.rag_sources?.length) {
        setRagSources(data.rag_sources);
      }
      if (data.booked_appointment) {
        setBookedAppointment(data.booked_appointment);
      }
      setTranscript((prev) => [
        ...prev,
        {
          role: "assistant",
          text: data.assistant_text,
          language: data.detected_language,
          timestamp: new Date().toISOString(),
        },
      ]);
      speakResponse(data.assistant_text, data.detected_language, data.audio_base64, data.audio_mime);
      onCrmUpdated?.();
    },
    [onCrmUpdated, speakResponse]
  );

  const stopMic = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.onend = null;
        recognitionRef.current.stop();
      } catch {
        // Ignore stop errors if already stopped
      }
      recognitionRef.current = null;
    }
    setIsMicOn(false);
    setInterimText("");
  }, []);

  const startCall = useCallback(
    async ({ callMode = mode, prospectName = "", company = "", languageHint = "" } = {}) => {
      setError("");
      stopPlayback();
      stopMic();
      setLatestInsight(null);
      setBookedAppointment(null);
      setToolEvents([]);
      setRagSources([]);
      setBargeInCount(0);
      setCallStatus("connecting");

      try {
        const res = await api.startCall({
          mode: callMode,
          prospect_name: prospectName || null,
          company: company || null,
          language_hint: languageHint || null,
        });
        setSessionId(res.session_id);
        setMode(callMode);
        setBant(res.bant || { lead_score: 15 });
        setSentiment(res.sentiment || "Neutral");
        setDetectedLanguage(res.detected_language || "English");
        setTranscript([
          {
            role: "assistant",
            text: res.greeting,
            language: res.detected_language || "English",
            timestamp: new Date().toISOString(),
          },
        ]);

        const ws = new WebSocket(buildWsUrl(res.session_id));
        wsRef.current = ws;
        ws.onmessage = (event) => {
          const msg = JSON.parse(event.data);
          if (msg.type === "agent_turn") {
            handleAgentPayload(msg.data);
          } else if (msg.type === "interrupted") {
            setCallStatus("active");
          } else if (msg.type === "insights_ready") {
            setLatestInsight(msg.data);
            setCallStatus("ended");
            onInsightsReady?.(msg.data);
          } else if (msg.type === "error") {
            setError(msg.detail || "WebSocket agent error");
            setCallStatus("active");
          }
        };
        ws.onerror = () => {
          // Non-fatal: sendUserMessage gracefully falls back to REST
        };

        setCallStatus("active");
        speakResponse(res.greeting, res.detected_language, res.audio_base64, res.audio_mime);
      } catch (err) {
        setError(err.message || "Failed to start call session");
        setCallStatus("idle");
      }
    },
    [handleAgentPayload, mode, onInsightsReady, speakResponse, stopMic, stopPlayback]
  );

  const sendUserMessage = useCallback(
    async (text) => {
      const cleaned = text.trim();
      if (!cleaned || !sessionId || callStatusRef.current === "ended") return;

      triggerBargeIn();
      setError("");
      setTranscript((prev) => [
        ...prev,
        {
          role: "user",
          text: cleaned,
          language: detectedLanguage,
          timestamp: new Date().toISOString(),
        },
      ]);
      setCallStatus("thinking");

      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "user_text", text: cleaned }));
        return;
      }

      try {
        const res = await api.sendTurnRest(sessionId, cleaned);
        handleAgentPayload(res);
      } catch (err) {
        setError(err.message || "Failed to process message");
        setCallStatus("active");
      }
    },
    [detectedLanguage, handleAgentPayload, sessionId, triggerBargeIn]
  );

  const toggleMic = useCallback(() => {
    if (isMicOn) {
      stopMic();
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setError("Browser Web Speech API is unavailable here. Use the text fallback input below.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = LANG_TO_BCP47[detectedLanguage] || "en-US";

    recognition.onspeechstart = () => {
      if (isSpeakingRef.current) {
        triggerBargeIn();
      }
    };

    recognition.onresult = (event) => {
      if (isSpeakingRef.current) {
        triggerBargeIn();
      }
      let interim = "";
      let finalChunk = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const piece = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalChunk += piece;
        } else {
          interim += piece;
        }
      }
      setInterimText(interim);
      if (finalChunk.trim()) {
        setInterimText("");
        sendUserMessage(finalChunk.trim());
      }
    };

    recognition.onerror = (event) => {
      if (event.error !== "no-speech" && event.error !== "aborted") {
        setError(`Mic error: ${event.error}. Text fallback remains active.`);
      }
    };

    recognition.onend = () => {
      if (recognitionRef.current === recognition && callStatusRef.current === "active") {
        try {
          recognition.start();
        } catch {
          setIsMicOn(false);
        }
      } else {
        setIsMicOn(false);
      }
    };

    recognitionRef.current = recognition;
    recognition.start();
    setIsMicOn(true);
    setError("");
  }, [detectedLanguage, isMicOn, sendUserMessage, stopMic, triggerBargeIn]);

  const endCall = useCallback(async () => {
    if (!sessionId) return;
    stopPlayback();
    stopMic();
    setCallStatus("ended");

    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch {
        // Ignore close error
      }
      wsRef.current = null;
    }

    try {
      const res = await api.endCall(sessionId, true);
      if (res.insight) {
        setLatestInsight(res.insight);
        onInsightsReady?.(res.insight);
      }
      onCrmUpdated?.();
    } catch (err) {
      setError(err.message || "Failed to generate post-call insights");
    }
  }, [onCrmUpdated, onInsightsReady, sessionId, stopMic, stopPlayback]);

  useEffect(() => {
    return () => {
      stopPlayback();
      stopMic();
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [stopMic, stopPlayback]);

  return {
    sessionId,
    callStatus,
    mode,
    setMode,
    transcript,
    interimText,
    bant,
    sentiment,
    detectedLanguage,
    toolEvents,
    ragSources,
    bookedAppointment,
    latestInsight,
    isMicOn,
    isSpeaking,
    bargeInCount,
    error,
    startCall,
    sendUserMessage,
    toggleMic,
    triggerBargeIn,
    endCall,
  };
}
