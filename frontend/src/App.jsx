import { useCallback, useEffect, useState } from "react";
import { BarChart2, Database, Headphones, Phone } from "lucide-react";
import { api } from "./api/client";
import { useVoiceCall } from "./hooks/useVoiceCall";
import CallConsole from "./components/CallConsole";
import BantInspector from "./components/BantInspector";
import CrmDashboard from "./components/CrmDashboard";
import InsightsDashboard from "./components/InsightsDashboard";

export default function App() {
  const [activeTab, setActiveTab] = useState("call"); // call | crm | insights
  const [health, setHealth] = useState(null);
  const [leads, setLeads] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [slots, setSlots] = useState([]);
  const [insights, setInsights] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loadingCrm, setLoadingCrm] = useState(false);

  const refreshData = useCallback(async () => {
    setLoadingCrm(true);
    try {
      const [h, l, a, s, ins, an] = await Promise.all([
        api.health(),
        api.getLeads(),
        api.getAppointments(),
        api.getSlots(),
        api.getInsights(),
        api.getAnalytics(),
      ]);
      setHealth(h);
      setLeads(l);
      setAppointments(a);
      setSlots(s);
      setInsights(ins);
      setAnalytics(an);
    } catch {
      // Backend might still be starting during initial load
    } finally {
      setLoadingCrm(false);
    }
  }, []);

  useEffect(() => {
    refreshData();
  }, [refreshData]);

  const voice = useVoiceCall({
    onCrmUpdated: refreshData,
    onInsightsReady: refreshData,
  });

  const tabs = [
    { id: "call", label: "Live Call Simulator", icon: Phone },
    { id: "crm", label: `CRM & Calendar (${leads.length})`, icon: Database },
    { id: "insights", label: `Post-Call Insights (${insights.length})`, icon: BarChart2 },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Navbar */}
      <header className="border-b border-slate-800/90 bg-slate-900/80 backdrop-blur sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-950">
              <Headphones className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-base font-bold tracking-tight text-white">NovaFlow AI</h1>
              <p className="text-[11px] text-slate-400">Autonomous Sales Voice Agent MVP</p>
            </div>
          </div>

          {/* Runtime Provider Badges */}
          {health && (
            <div className="hidden md:flex items-center gap-2 text-[11px]">
              <span className="px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700 text-slate-300">
                LLM: <strong className="text-indigo-300">{health.llm_provider}</strong>
              </span>
              <span className="px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700 text-slate-300">
                STT: <strong className="text-emerald-300">{health.stt_provider}</strong>
              </span>
              <span className="px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700 text-slate-300">
                TTS: <strong className="text-sky-300">{health.tts_provider}</strong>
              </span>
              <span className="px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700 text-slate-300">
                RAG KB: <strong className="text-amber-300">{health.kb_chunks} chunks</strong>
              </span>
            </div>
          )}

          {/* Navigation Tabs */}
          <nav className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                    active ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {tab.label}
                </button>
              );
            })}
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6">
        {activeTab === "call" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
            <div className="lg:col-span-7">
              <CallConsole voice={voice} />
            </div>
            <div className="lg:col-span-5">
              <BantInspector voice={voice} />
            </div>
          </div>
        )}

        {activeTab === "crm" && (
          <CrmDashboard
            leads={leads}
            appointments={appointments}
            slots={slots}
            onRefresh={refreshData}
            loading={loadingCrm}
          />
        )}

        {activeTab === "insights" && (
          <InsightsDashboard analytics={analytics} insights={insights} />
        )}
      </main>
    </div>
  );
}
