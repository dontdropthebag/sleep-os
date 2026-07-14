"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { apiGet } from "@/lib/api";
import { Card, ConfidenceBadge, Disclaimer, Empty, Stat } from "@/components/ui";

export default function SnoringPage() {
  const [d, setD] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet("/api/metrics/snoring").then(setD).catch((e) => setError(String(e)));
  }, []);

  if (error) return <Empty message={`Backend not reachable (${error}).`} />;
  if (!d) return <Empty message="Loading…" />;

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-bold">Snoring & breathing</h1>
        <p className="text-sm text-slate-400">
          Device-estimated snoring from your sleep tracker. Detection is conservative and low-confidence.
        </p>
      </header>

      {d.status !== "ok" ? (
        <Card title="Not enough data yet"><p className="text-sm text-slate-400">{d.note}</p></Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Nights with data" value={d.nights_with_snore_data} />
            <Stat label="Average snoring" value={`${d.avg_snore_min} min`} />
            <Stat label="Median" value={`${d.median_snore_min} min`} />
            <Stat label="Heavier nights (>15% of night)" value={d.heavy_nights} />
          </div>

          <Card title="Snoring per night" subtitle="Minutes of detected snoring (device estimate).">
            <div className="h-56" role="img"
                 aria-label={`Snoring trend over ${d.nights_with_snore_data} nights, averaging ${d.avg_snore_min} minutes.`}>
              <ResponsiveContainer>
                <BarChart data={d.trend.map((t: any) => ({ date: t.date.slice(5), min: t.snore_min }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#94a3b8" }} />
                  <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} unit="m" />
                  <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155" }} />
                  <Bar dataKey="min" fill="#fb923c" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2"><ConfidenceBadge level={d.detection_confidence} /></div>
          </Card>
        </>
      )}

      <Card title="When to consider a medical review">
        <p className="text-sm leading-relaxed text-slate-300">
          {d.medical_note ??
            "Snoring alone does not diagnose sleep apnea, and a phone or wearable cannot confirm or exclude it. If snoring is combined with witnessed breathing pauses, gasping or choking, significant daytime sleepiness, repeated morning headaches, or waking with a racing heart, a conversation with a healthcare professional about a sleep assessment would be reasonable."}
        </p>
      </Card>
      <Disclaimer />
    </div>
  );
}
