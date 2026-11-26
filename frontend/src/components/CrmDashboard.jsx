import { Calendar, RefreshCw, Users } from "lucide-react";

export default function CrmDashboard({ leads, appointments, slots, onRefresh, loading }) {
  const openSlots = slots.filter((s) => s.available);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">CRM Leads & Demo Calendar</h2>
          <p className="text-xs text-slate-400">
            All BANT attributes are normalized to English in SQLite regardless of call language.
          </p>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-medium text-slate-200 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh CRM
        </button>
      </div>

      {/* Leads Table */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-800 flex items-center gap-2">
          <Users className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-semibold text-white">Qualified Pipeline ({leads.length})</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/70 text-slate-400 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3">Lead / Company</th>
                <th className="px-4 py-3">Budget & Timeline</th>
                <th className="px-4 py-3">Need</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Sentiment</th>
                <th className="px-4 py-3">Lang</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70">
              {leads.map((lead) => (
                <tr key={lead.id} className="hover:bg-slate-800/30">
                  <td className="px-4 py-3">
                    <div className="font-semibold text-white">{lead.name || "Unnamed Prospect"}</div>
                    <div className="text-slate-400">
                      {lead.role ? `${lead.role} · ` : ""}
                      {lead.company || "Unknown Co."}
                    </div>
                    {lead.email && <div className="text-[11px] text-indigo-400">{lead.email}</div>}
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-slate-200">{lead.budget || "TBD"}</div>
                    <div className="text-slate-400">{lead.timeline || "TBD"}</div>
                  </td>
                  <td className="px-4 py-3 max-w-xs">
                    <p className="text-slate-300 line-clamp-2">{lead.need || "Discovery in progress"}</p>
                  </td>
                  <td className="px-4 py-3 font-semibold text-white">{lead.lead_score}/100</td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-200 border border-slate-700">
                      {lead.sentiment}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-300">{lead.detected_language}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded-full font-medium ${
                        lead.status === "Demo Booked"
                          ? "bg-emerald-500/20 text-emerald-300"
                          : lead.status === "Qualified"
                          ? "bg-sky-500/20 text-sky-300"
                          : "bg-slate-800 text-slate-300"
                      }`}
                    >
                      {lead.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Appointments & Open AE Slots */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-semibold text-white">
              Confirmed Demo Appointments ({appointments.length})
            </h3>
          </div>
          <div className="space-y-2.5">
            {appointments.map((appt) => (
              <div
                key={appt.id}
                className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 space-y-1 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-white">
                    {appt.lead_name || "Prospect"} — {appt.company || "Company"}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
                    {appt.status}
                  </span>
                </div>
                <div className="text-indigo-300 font-medium">{appt.slot_label}</div>
                <div className="text-slate-400">Owner: {appt.ae_owner}</div>
                <div className="text-slate-500 font-mono truncate">{appt.meeting_link}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 space-y-3">
          <h3 className="text-sm font-semibold text-white">
            Available AE Calendar Slots ({openSlots.length} open)
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {openSlots.slice(0, 8).map((slot) => (
              <div
                key={slot.slot_iso}
                className="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800 text-xs"
              >
                <div className="font-medium text-slate-200">{slot.slot_label}</div>
                <div className="text-[11px] text-slate-400 truncate">{slot.ae_owner}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
