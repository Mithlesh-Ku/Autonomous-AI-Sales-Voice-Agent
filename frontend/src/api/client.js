const API_BASE = import.meta.env.VITE_API_BASE || "";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(errText || `HTTP ${res.status}`);
  }
  return res.json();
}

export function buildWsUrl(sessionId) {
  const explicit = import.meta.env.VITE_WS_BASE;
  if (explicit) {
    return `${explicit}/ws/call/${sessionId}`;
  }
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws/call/${sessionId}`;
}

export const api = {
  health: () => request("/api/health"),
  startCall: (payload) =>
    request("/api/calls/start", { method: "POST", body: JSON.stringify(payload) }),
  sendTurnRest: (sessionId, text, language = null) =>
    request(`/api/calls/${sessionId}/turn`, {
      method: "POST",
      body: JSON.stringify({ text, language }),
    }),
  endCall: (sessionId, wait = true) =>
    request(`/api/calls/${sessionId}/end?wait=${wait}`, { method: "POST" }),
  getLeads: () => request("/api/leads"),
  getAppointments: () => request("/api/appointments"),
  getSlots: () => request("/api/appointments/slots"),
  getInsights: () => request("/api/insights"),
  getAnalytics: () => request("/api/analytics"),
};
