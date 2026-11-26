import { CalendarCheck, Cpu, Globe, TrendingUp, Wrench } from "lucide-react";

const SENTIMENT_STYLE = {
  "Ready to Buy": "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  Positive: "bg-sky-500/20 text-sky-300 border-sky-500/40",
  Neutral: "bg-slate-700/50 text-slate-300 border-slate-600",
  Skeptical: "bg-amber-500/20 text-amber-300 border-amber-500/40",
  Frustrated: "bg-rose-500/20 text-rose-300 border-rose-500/40",
};

export default function BantInspector({ voice }) {
  const bant = voice.bant || {};
  const score = Number(bant.lead_score ?? 15);
  const scoreColor =
    score >= 75 ? "bg-emerald-500" : score >= 50 ? "bg-amber-400" : "bg-indigo-500";

  const fields = [
    { label: "Prospect", value: bant.name },
    { label: "Email", value: bant.email },
    { label: "Company", value: bant.company },
    { label: "Role", value: bant.role },
    { label: "Budget", value: bant.budget },
    { label: "Authority", value: bant.authority },
    { label: "Need", value: bant.need },
    { label: "Timeline", value: bant.timeline },
  ];

  return (
    <div className="space-y-4">
      {/* Live Score & Signals Card */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-indigo-400" />
            <h3 className="text-sm font-semibold text-white">Live Lead Qualification (BANT)</h3>
          </div>
          <span className="text-lg font-bold text-white">{score}/100</span>
        </div>

        <div className="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden">
          <div
            className={`h-full ${scoreColor} transition-all duration-500`}
            style={{ width: `${Math.min(100, Math.max(5, score))}%` }}
          />
        </div>

        <div className="flex flex-wrap gap-2">
          <span
            className={`text-xs font-medium px-2.5 py-1 rounded-full border ${
              SENTIMENT_STYLE[voice.sentiment] || SENTIMENT_STYLE.Neutral
            }`}
          >
            Sentiment: {voice.sentiment}
          </span>
          <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
            <Globe className="w-3 h-3" />
            {voice.detectedLanguage}
          </span>
        </div>

        {/* Structured BANT Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
          {fields.map((f) => (
            <div
              key={f.label}
              className="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800/90"
            >
              <div className="text-[11px] uppercase tracking-wider text-slate-500">{f.label}</div>
              <div className="text-xs font-medium text-slate-200 mt-0.5 truncate" title={f.value || ""}>
                {f.value || <span className="text-slate-600 italic">Pending...</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Confirmed Appointment Card */}
      {voice.bookedAppointment && (
        <div className="bg-emerald-950/35 border border-emerald-500/40 rounded-2xl p-4 space-y-2">
          <div className="flex items-center gap-2 text-emerald-300 font-semibold text-sm">
            <CalendarCheck className="w-4 h-4" />
            Demo Autonomously Booked
          </div>
          <div className="text-xs text-slate-200 space-y-1">
            <div>
              <span className="text-slate-400">Slot:</span> {voice.bookedAppointment.slot_label}
            </div>
            <div>
              <span className="text-slate-400">AE Owner:</span> {voice.bookedAppointment.ae_owner}
            </div>
            <div className="truncate">
              <span className="text-slate-400">Link:</span>{" "}
              <span className="text-emerald-300 font-mono">{voice.bookedAppointment.meeting_link}</span>
            </div>
          </div>
        </div>
      )}

      {/* RAG Sources & Tool Activity */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-sky-400" />
          <h3 className="text-sm font-semibold text-white">LangGraph Tool & RAG Trace</h3>
        </div>

        {voice.ragSources?.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {voice.ragSources.map((src, i) => (
              <span
                key={i}
                className="text-[11px] px-2 py-0.5 rounded bg-sky-500/15 text-sky-300 border border-sky-500/30"
              >
                RAG: {src}
              </span>
            ))}
          </div>
        )}

        <div className="space-y-2 max-h-48 overflow-y-auto">
          {voice.toolEvents?.length === 0 ? (
            <p className="text-xs text-slate-500 italic">
              Tool executions (RAG lookup, slot check, CRM upsert, booking) appear here live.
            </p>
          ) : (
            voice.toolEvents.map((ev, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2 text-xs p-2 rounded-lg bg-slate-950/70 border border-slate-800"
              >
                <Wrench className="w-3.5 h-3.5 text-indigo-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-mono text-indigo-300">{ev.tool}</span>
                  <p className="text-slate-400">{ev.summary}</p>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
