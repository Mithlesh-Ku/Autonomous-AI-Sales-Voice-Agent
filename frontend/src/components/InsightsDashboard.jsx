import { BarChart3, CheckCircle2, FileText, ShieldAlert } from "lucide-react";

export default function InsightsDashboard({ analytics, insights }) {
  const kpis = [
    { label: "Total CRM Leads", value: analytics?.total_leads ?? 0, accent: "text-white" },
    { label: "Qualified Leads", value: analytics?.qualified_leads ?? 0, accent: "text-sky-400" },
    { label: "Booked Demos", value: analytics?.booked_demos ?? 0, accent: "text-emerald-400" },
    {
      label: "Avg Lead Score",
      value: `${analytics?.avg_lead_score ?? 0}/100`,
      accent: "text-indigo-400",
    },
    {
      label: "Avg Win Probability",
      value: `${analytics?.avg_conversion_probability ?? 0}%`,
      accent: "text-amber-300",
    },
  ];

  const sentimentEntries = Object.entries(analytics?.sentiment_breakdown || {});
  const languageEntries = Object.entries(analytics?.language_breakdown || {});

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white">Post-Call Insights & Revenue Analytics</h2>
        <p className="text-xs text-slate-400">
          Generated asynchronously whenever a call ends — surfacing objections, next best actions, and win probability.
        </p>
      </div>

      {/* KPI Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {kpis.map((k) => (
          <div
            key={k.label}
            className="bg-slate-900/70 border border-slate-800 rounded-2xl p-4"
          >
            <div className="text-xs text-slate-400">{k.label}</div>
            <div className={`text-2xl font-bold mt-1 ${k.accent}`}>{k.value}</div>
          </div>
        ))}
      </div>

      {/* Distribution Bars */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <BarChart3 className="w-4 h-4 text-indigo-400" />
            Sentiment Distribution
          </div>
          <div className="space-y-2">
            {sentimentEntries.map(([label, count]) => (
              <div key={label} className="flex items-center gap-3 text-xs">
                <span className="w-24 text-slate-300">{label}</span>
                <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-indigo-500"
                    style={{
                      width: `${Math.min(100, (count / Math.max(1, analytics?.total_leads || 1)) * 100)}%`,
                    }}
                  />
                </div>
                <span className="w-6 text-right text-slate-400">{count}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <BarChart3 className="w-4 h-4 text-emerald-400" />
            Multilingual Call Mix
          </div>
          <div className="space-y-2">
            {languageEntries.map(([lang, count]) => (
              <div key={lang} className="flex items-center gap-3 text-xs">
                <span className="w-24 text-slate-300">{lang}</span>
                <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-emerald-500"
                    style={{
                      width: `${Math.min(100, (count / Math.max(1, analytics?.total_leads || 1)) * 100)}%`,
                    }}
                  />
                </div>
                <span className="w-6 text-right text-slate-400">{count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Post-Call Insight Cards */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <FileText className="w-4 h-4 text-sky-400" />
          Executive Call Summaries ({insights.length})
        </h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {insights.map((item) => (
            <div
              key={item.id}
              className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 space-y-3"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h4 className="font-semibold text-white">
                    {item.lead_name || "Prospect"}{" "}
                    <span className="text-slate-400 font-normal">
                      {item.company ? `· ${item.company}` : ""}
                    </span>
                  </h4>
                  <div className="text-[11px] text-slate-500 font-mono">
                    {item.session_id} · {item.detected_language} · Score {item.lead_score_final}/100
                  </div>
                </div>
                <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300">
                  {item.conversion_probability}% Win Prob.
                </span>
              </div>

              <p className="text-xs text-slate-300 leading-relaxed">{item.executive_summary}</p>

              {item.key_objections?.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[11px] uppercase tracking-wider text-amber-300 flex items-center gap-1">
                    <ShieldAlert className="w-3.5 h-3.5" />
                    Key Objections
                  </div>
                  <ul className="list-disc list-inside text-xs text-slate-400 space-y-0.5">
                    {item.key_objections.map((obj, idx) => (
                      <li key={idx}>{obj}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800 text-xs text-emerald-300 flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold">Next Best Action:</span> {item.next_best_action}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
