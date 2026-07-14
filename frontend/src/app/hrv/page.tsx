"use client";

import { useEffect, useState } from "react";
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { apiGet } from "@/lib/api";
import { Card, ConfidenceBadge, Disclaimer, Empty, Stat } from "@/components/ui";

export default function HrvPage() {
  const [hrv, setHrv] = useState<any>(null);
  const [rhr, setRhr] = useState<any>(null);
  const [sessions, setSessions] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      apiGet("/api/metrics/baselines/hrv_rmssd"),
      apiGet("/api/metrics/baselines/resting_hr"),
      apiGet("/api/sessions?days=28&include_naps=false"),
    ]).then(([h, r, s]) => { setHrv(h); setRhr(r); setSessions(s); })
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <Empty message={`Backend not reachable (${error}).`} />;
  if (!hrv) return <Empty message="Loading…" />;

  const renderBaseline = (b: any, label: string) => {
    if (b.status !== "ok")
      return (
        <Card title={label}>
          <p className="text-sm leading-relaxed text-slate-400">
            No HRV-capable device connected yet — Sleep as Android doesn&apos;t record{" "}
            {label.includes("HRV") ? "HRV" : "this metric"}. When you get an Oura Ring, WHOOP or
            Garmin, drop its export into the <a href="/import" className="text-sky-400 hover:underline">Import</a>{" "}
            screen and your personal baselines (7/28/60-day medians) will appear here
            automatically. Different devices are kept separate and never blended.
          </p>
        </Card>
      );
    const g = b.preferred;
    return (
      <Card title={`${label} — ${g.source} (${g.method})`}
            subtitle="Personal trend vs your own baseline. Not compared to population averages.">
        <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Latest" value={`${g.current} ${g.unit ?? ""}`} hint={g.current_date} />
          <Stat label="7-day median" value={g.median_7d ?? "—"} />
          <Stat label="28-day median" value={g.median_28d ?? "—"} />
          <Stat label="vs baseline" value={g.deviation_from_baseline != null ? `${g.deviation_from_baseline > 0 ? "+" : ""}${g.deviation_from_baseline}` : "—"}
                hint={g.flag?.replace(/_/g, " ")} />
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <ConfidenceBadge level={g.confidence} />
          {b.note && <span>{b.note}</span>}
        </div>
      </Card>
    );
  };

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-bold">HRV & recovery</h1>
        <p className="text-sm text-slate-400">
          Estimated physiological recovery — interpreted against your own baseline alongside sleep,
          training, alcohol and travel. A low value is context, not a diagnosis.
        </p>
      </header>
      {renderBaseline(hrv, "HRV (rMSSD)")}
      {rhr && renderBaseline(rhr, "Resting heart rate")}

      {sessions.length > 0 && (
        <Card title="Sleep duration context" subtitle="Recovery metrics should be read alongside recent sleep.">
          <div className="h-48" role="img" aria-label="Sleep duration for recent nights.">
            <ResponsiveContainer>
              <LineChart data={sessions.map((s) => ({ date: s.session_date.slice(5), h: s.total_sleep_min != null ? +(s.total_sleep_min / 60).toFixed(1) : null }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#94a3b8" }} />
                <YAxis domain={[4, 10]} tick={{ fontSize: 11, fill: "#94a3b8" }} unit="h" />
                <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155" }} />
                <ReferenceLine y={8} stroke="#334155" strokeDasharray="4 4" />
                <Line type="monotone" dataKey="h" stroke="#a78bfa" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}
      <Disclaimer />
    </div>
  );
}
