import { useEffect, useRef, useState } from "react";
import {
  Keyboard,
  Mic,
  MicOff,
  PhoneCall,
  PhoneOff,
  Send,
  Sparkles,
  Volume2,
  Zap,
} from "lucide-react";

const DEMO_SCRIPTS = [
  {
    label: "1. Discovery + BANT",
    text: "Hi, I'm David Chen, VP of RevOps at OrbitScale. We have 35 AEs wasting hours updating Salesforce and a $40,000 budget to fix this next month.",
  },
  {
    label: "2. Pricing & RAG",
    text: "How much does your Growth plan cost and how does it compare to Salesforce native workflows?",
  },
  {
    label: "3. Security Objection",
    text: "Our InfoSec team is strict about SOC 2 compliance and AI data privacy. How do you handle that?",
  },
  {
    label: "4. Book Demo",
    text: "That makes sense. Can we schedule a live demo? My email is david.chen@orbitscale.io",
  },
  {
    label: "5. Confirm Slot",
    text: "Yes please, book the first open slot for me!",
  },
  {
    label: "6. Spanish Test",
    text: "Hola, somos 25 personas en nuestro equipo de ventas y queremos ver precios y una demo.",
  },
  {
    label: "7. Hindi Test",
    text: "Namaste, hamari team mein 20 reps hain. Growth plan ka price kitna hai aur kya demo mil sakta hai?",
  },
];

export default function CallConsole({ voice }) {
  const [textInput, setTextInput] = useState("");
  const [textFallbackOpen, setTextFallbackOpen] = useState(true);
  const [prospectName, setProspectName] = useState("");
  const [company, setCompany] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [voice.transcript, voice.interimText]);

  const isLive = voice.callStatus === "active" || voice.callStatus === "thinking";

  const handleSend = (e) => {
    e.preventDefault();
    if (!textInput.trim()) return;
    voice.sendUserMessage(textInput);
    setTextInput("");
  };

  return (
    <div className="flex flex-col h-[calc(100vh-12rem)] min-h-[600px] bg-slate-900/70 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
      {/* Call Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 bg-slate-900 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div
            className={`w-3 h-3 rounded-full ${
              isLive
                ? "bg-emerald-400 animate-pulse shadow-[0_0_12px_#34d399]"
                : voice.callStatus === "ended"
                ? "bg-amber-400"
                : "bg-slate-500"
            }`}
          />
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-semibold text-white">Live Voice Call Simulator</h2>
              {voice.sessionId && (
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                  {voice.sessionId}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400">
              {voice.isSpeaking
                ? "Ava is speaking (speak or click Interrupt to barge in)"
                : voice.callStatus === "thinking"
                ? "Ava is reasoning + querying RAG / CRM..."
                : isLive
                ? "Call active — streaming transcript & real-time BANT"
                : "Ready to start an inbound or outbound B2B sales simulation"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {!isLive && (
            <div className="flex rounded-lg bg-slate-800 p-0.5 border border-slate-700 text-xs">
              {["inbound", "outbound"].map((m) => (
                <button
                  key={m}
                  onClick={() => voice.setMode(m)}
                  className={`px-3 py-1.5 rounded-md capitalize font-medium transition ${
                    voice.mode === m ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          )}

          {!isLive ? (
            <button
              onClick={() =>
                voice.startCall({
                  callMode: voice.mode,
                  prospectName,
                  company,
                })
              }
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold transition shadow-lg shadow-emerald-950/50"
            >
              <PhoneCall className="w-4 h-4" />
              Start {voice.mode === "inbound" ? "Inbound" : "Outbound"} Call
            </button>
          ) : (
            <>
              <button
                onClick={voice.toggleMic}
                className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium border transition ${
                  voice.isMicOn
                    ? "bg-rose-500/20 border-rose-500/50 text-rose-300"
                    : "bg-slate-800 border-slate-700 text-slate-200 hover:bg-slate-700"
                }`}
              >
                {voice.isMicOn ? <Mic className="w-4 h-4 animate-pulse" /> : <MicOff className="w-4 h-4" />}
                {voice.isMicOn ? "Mic Live" : "Enable Mic"}
              </button>

              {voice.isSpeaking && (
                <button
                  onClick={voice.triggerBargeIn}
                  className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-amber-500/20 border border-amber-500/50 text-amber-300 text-sm font-medium hover:bg-amber-500/30 transition"
                >
                  <Zap className="w-4 h-4" />
                  Barge-In
                </button>
              )}

              <button
                onClick={voice.endCall}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-sm font-semibold transition"
              >
                <PhoneOff className="w-4 h-4" />
                End Call
              </button>
            </>
          )}
        </div>
      </div>

      {/* Optional Prospect Pre-Call Config */}
      {!isLive && voice.transcript.length === 0 && (
        <div className="px-5 py-3 bg-slate-900/50 border-b border-slate-800/80 flex flex-wrap gap-3 items-center text-xs">
          <span className="text-slate-400 font-medium">Optional Caller Context:</span>
          <input
            type="text"
            value={prospectName}
            onChange={(e) => setProspectName(e.target.value)}
            placeholder="Prospect Name (e.g. Jordan Lee)"
            className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
          <input
            type="text"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="Company (e.g. Acme Cloud)"
            className="px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>
      )}

      {/* Voice Waveform + Barge-In Banner */}
      {isLive && (
        <div className="px-5 py-2.5 bg-slate-950/60 border-b border-slate-800/70 flex items-center justify-between text-xs">
          <div className="flex items-center gap-3">
            <Volume2 className={`w-4 h-4 ${voice.isSpeaking ? "text-indigo-400" : "text-slate-500"}`} />
            <div className="flex items-end gap-1 h-4">
              {[0, 1, 2, 3, 4, 5].map((bar) => (
                <span
                  key={bar}
                  style={{ animationDelay: `${bar * 120}ms` }}
                  className={`w-1 rounded-full transition-all ${
                    voice.isSpeaking
                      ? "h-4 bg-indigo-400 voice-bar"
                      : voice.isMicOn
                      ? "h-3 bg-emerald-400 voice-bar"
                      : "h-1.5 bg-slate-700"
                  }`}
                />
              ))}
            </div>
            <span className="text-slate-400">
              {voice.isSpeaking
                ? "TTS Audio Playing"
                : voice.isMicOn
                ? "Listening via Web Speech STT..."
                : "Text-Fallback Ready"}
            </span>
          </div>
          <div className="flex items-center gap-3">
            {voice.bargeInCount > 0 && (
              <span className="px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30">
                Interruptions: {voice.bargeInCount}
              </span>
            )}
            <button
              onClick={() => setTextFallbackOpen((v) => !v)}
              className="inline-flex items-center gap-1 text-slate-400 hover:text-white"
            >
              <Keyboard className="w-3.5 h-3.5" />
              {textFallbackOpen ? "Hide Text Input" : "Show Text Input"}
            </button>
          </div>
        </div>
      )}

      {/* Error Alert */}
      {voice.error && (
        <div className="mx-5 mt-3 px-3 py-2 rounded-lg bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs">
          {voice.error}
        </div>
      )}

      {/* Real-Time Transcript Stream */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {voice.transcript.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto space-y-3">
            <div className="w-12 h-12 rounded-2xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Sparkles className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-white">Autonomous B2B Sales Voice Agent</h3>
            <p className="text-sm text-slate-400">
              Click <span className="text-emerald-400 font-medium">Start Inbound Call</span> to test live voice capture,
              RAG-grounded pricing answers, multilingual detection, BANT scoring, and autonomous demo booking.
            </p>
          </div>
        ) : (
          voice.transcript.map((turn, idx) => {
            const isUser = turn.role === "user";
            return (
              <div key={idx} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    isUser
                      ? "bg-indigo-600 text-white rounded-br-sm"
                      : "bg-slate-800/90 border border-slate-700/80 text-slate-100 rounded-bl-sm"
                  }`}
                >
                  <div className="flex items-center justify-between gap-4 mb-1 text-[11px] opacity-75">
                    <span className="font-semibold">{isUser ? "Prospect" : "Ava (NovaFlow AI)"}</span>
                    <span>{turn.language}</span>
                  </div>
                  <p>{turn.text}</p>
                </div>
              </div>
            );
          })
        )}

        {voice.interimText && (
          <div className="flex justify-end">
            <div className="max-w-[80%] rounded-2xl px-4 py-2.5 text-sm bg-indigo-600/40 border border-indigo-500/40 text-indigo-200 italic">
              {voice.interimText}...
            </div>
          </div>
        )}

        {voice.callStatus === "thinking" && (
          <div className="flex justify-start">
            <div className="rounded-2xl px-4 py-2.5 text-xs bg-slate-800/70 border border-slate-700 text-slate-400 animate-pulse">
              Ava is thinking, updating CRM & searching knowledge base...
            </div>
          </div>
        )}

        {voice.latestInsight && (
          <div className="rounded-xl p-4 bg-emerald-950/40 border border-emerald-500/40 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-emerald-300">
                Post-Call Insight Generated
              </span>
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
                {voice.latestInsight.conversion_probability}% Conversion Prob.
              </span>
            </div>
            <p className="text-sm text-slate-200">{voice.latestInsight.executive_summary}</p>
            <p className="text-xs text-emerald-300">
              <span className="font-semibold">Next Best Action:</span> {voice.latestInsight.next_best_action}
            </p>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Quick Demo Prompts + Text Input Fallback */}
      {isLive && textFallbackOpen && (
        <div className="border-t border-slate-800 bg-slate-900/90 p-3 space-y-2.5">
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
            <span className="text-[11px] text-slate-500 shrink-0 mr-1">Demo Turns:</span>
            {DEMO_SCRIPTS.map((item) => (
              <button
                key={item.label}
                type="button"
                onClick={() => voice.sendUserMessage(item.text)}
                className="shrink-0 text-[11px] px-2.5 py-1 rounded-full bg-slate-800 hover:bg-indigo-600/30 border border-slate-700 hover:border-indigo-500/50 text-slate-300 transition"
              >
                {item.label}
              </button>
            ))}
          </div>

          <form onSubmit={handleSend} className="flex gap-2">
            <input
              type="text"
              value={textInput}
              onChange={(e) => {
                if (voice.isSpeaking) voice.triggerBargeIn();
                setTextInput(e.target.value);
              }}
              placeholder="Type a prospect response (triggers barge-in if Ava is speaking)..."
              className="flex-1 px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-700 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
            <button
              type="submit"
              disabled={!textInput.trim()}
              className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-sm font-medium inline-flex items-center gap-1.5 transition"
            >
              <Send className="w-4 h-4" />
              Send
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
