"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet, fmtMin, fmtTime } from "@/lib/api";
import { ConfidenceBadge, Empty } from "@/components/ui";

export default function NightsPage() {
  const [rows, setRows] = useState<any[] | null>(null);

  useEffect(() => {
    apiGet("/api/sessions?days=60").then((r) => setRows([...r].reverse())).catch(() => setRows([]));
  }, []);

  if (!rows) return <Empty message="Loading…" />;
  if (rows.length === 0) return <Empty message="No sleep sessions yet — import data or add a manual entry." />;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold">Nights</h1>
      <div className="overflow-x-auto rounded-xl border border-slate-700/60">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900 text-xs text-slate-400">
            <tr>
              <th className="p-2">Date</th><th className="p-2">Type</th><th className="p-2">In bed</th>
              <th className="p-2">Wake</th><th className="p-2">Asleep</th><th className="p-2">Efficiency</th>
              <th className="p-2">Source</th><th className="p-2">Data quality</th><th className="p-2"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.id} className="border-t border-slate-800 hover:bg-slate-900/50">
                <td className="p-2">{s.session_date}</td>
                <td className="p-2">{s.is_nap ? "nap" : "main"}</td>
                <td className="p-2">{fmtTime(s.in_bed_utc, s.timezone_name)}</td>
                <td className="p-2">{fmtTime(s.final_wake_utc, s.timezone_name)}</td>
                <td className="p-2">{fmtMin(s.total_sleep_min)}</td>
                <td className="p-2">{s.efficiency_pct != null ? `${s.efficiency_pct}%` : "—"}</td>
                <td className="p-2 text-xs">{s.source}{s.manually_edited ? " (edited)" : ""}</td>
                <td className="p-2"><ConfidenceBadge level={s.confidence} /></td>
                <td className="p-2"><Link className="text-sky-400 hover:underline" href={`/nights/${s.id}`}>detail</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
