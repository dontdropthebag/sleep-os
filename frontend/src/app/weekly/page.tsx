"use client";

import { useEffect, useState } from "react";
import { apiGet, fmtMin } from "@/lib/api";
import { Card, Disclaimer, Empty, Stat } from "@/components/ui";

export default function WeeklyPage() {
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet("/api/reports/weekly").then(setR).catch((e) => setError(String(e)));
  }, []);

  if (error) return <Empty message={`Backend not reachable (${error}).`} />;
  if (!r) return <Empty message="Loading…" />;
  if (r.status !== "ok") return <Empty message={r.note ?? "Not enough nights for a weekly report yet."} />;

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-bold">Weekly review</h1>
        <p className="text-sm text-slate-400">{r.note}</p>
      </header>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Average sleep" value={fmtMin(r.avg_total_sleep_min)} />
        <Stat label="Average efficiency" value={r.avg_efficiency_pct != null ? `${r.avg_efficiency_pct}%` : "—"} />
        <Stat label="Bedtime range" value={`${r.bedtime_range[0]}–${r.bedtime_range[1]}`} />
        <Stat label="Wake range" value={`${r.wake_range[0]}–${r.wake_range[1]}`} />
      </div>

      {r.patterns && (
        <Card title="Patterns & continuity" subtitle="Last 14 nights">
          <div className="flex flex-col gap-3 text-sm">
            {r.patterns.efficiency_trend && (
              <p>
                <span className="font-semibold text-slate-200">Sleep efficiency is {r.patterns.efficiency_trend.direction}</span>
                {" — "}{r.patterns.efficiency_trend.first_half_pct}% in the first week vs{" "}
                {r.patterns.efficiency_trend.second_half_pct}% in the most recent week
                {" "}({r.patterns.efficiency_trend.change_pct > 0 ? "+" : ""}{r.patterns.efficiency_trend.change_pct}%).
              </p>
            )}
            {r.patterns.circadian_rhythm && (
              <p>
                <span className="font-semibold text-slate-200">Circadian rhythm:</span>{" "}
                {r.patterns.circadian_rhythm.summary}
              </p>
            )}
            {r.patterns.irregular_bedtimes?.length > 0 ? (
              <div>
                <p className="font-semibold text-amber-300">Irregular bedtimes detected:</p>
                <ul className="mt-1 list-disc pl-5 text-slate-300">
                  {r.patterns.irregular_bedtimes.map((b: any, i: number) => (
                    <li key={i}>
                      {b.date}: in bed at {b.bedtime_local} ({b.deviation_min > 0 ? "+" : ""}{b.deviation_min} min vs your usual)
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-slate-400">No strongly irregular bedtimes in the last two weeks.</p>
            )}
          </div>
        </Card>
      )}

      <Card title="Regularity">
        {r.regularity.status === "ok" ? (
          <p className="text-sm">
            Bedtime varied by ±{Math.round(r.regularity.onset_sd_min)} min and wake time by
            ±{Math.round(r.regularity.wake_sd_min)} min this week
            {r.regularity.social_jetlag_min != null &&
              `; social jetlag ~${Math.abs(Math.round(r.regularity.social_jetlag_min))} min`}.
          </p>
        ) : (
          <p className="text-sm text-slate-500">Not enough nights for regularity stats.</p>
        )}
      </Card>

      <Card title="Sleep debt">
        {r.sleep_debt.status === "ok" ? (
          <>
            <p className="text-sm">
              Estimated rolling debt: <strong>{fmtMin(r.sleep_debt.net_debt_min)}</strong> over the last{" "}
              {r.sleep_debt.window} nights. <span className="text-xs text-slate-500">{r.sleep_debt.note}</span>
            </p>
            {r.sleep_debt_education && (
              <p className="mt-2 rounded-lg bg-slate-800/50 p-3 text-sm leading-relaxed text-slate-300">
                {r.sleep_debt_education}
              </p>
            )}
          </>
        ) : (
          <p className="text-sm text-slate-500">Not enough data.</p>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Card title="Best energy day">
          {r.best_energy_day ? (
            <p className="text-sm">{r.best_energy_day.date} — energy {r.best_energy_day.energy}/10</p>
          ) : <p className="text-sm text-slate-500">No morning check-ins this week.</p>}
        </Card>
        <Card title="Lowest energy day">
          {r.lowest_energy_day ? (
            <p className="text-sm">{r.lowest_energy_day.date} — energy {r.lowest_energy_day.energy}/10</p>
          ) : <p className="text-sm text-slate-500">No morning check-ins this week.</p>}
        </Card>
      </div>

      {r.data_quality_issues.length > 0 && (
        <Card title="Data-quality issues">
          <ul className="list-disc pl-5 text-sm text-amber-300/90">
            {r.data_quality_issues.map((q: string, i: number) => <li key={i}>{q}</li>)}
          </ul>
        </Card>
      )}

      <Card title="One focus for next week">
        <p className="text-sm font-medium text-sky-300">{r.recommended_focus}</p>
      </Card>
      <Disclaimer />
    </div>
  );
}
