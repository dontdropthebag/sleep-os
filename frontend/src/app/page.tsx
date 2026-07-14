"use client";

import { useEffect, useState } from "react";
import { apiGet, fmtMin, fmtTime } from "@/lib/api";
import { Card, ConfidenceBadge, Disclaimer, Empty, Stat } from "@/components/ui";

export default function TodayPage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet("/api/coaching/today").then(setData).catch((e) => setError(String(e)));
  }, []);

  if (error)
    return <Empty message={`Backend not reachable (${error}). Start it with: make backend`} />;
  if (!data) return <Empty message="Loading…" />;

  const c = data.coaching;
  const s = data.session;
  const t = c.tonights_target;

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-bold">Today</h1>
        <p className="text-sm text-slate-400">Morning coaching from last night&apos;s data</p>
      </header>

      {s && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Time asleep (device est.)" value={fmtMin(s.total_sleep_min)} />
          <Stat label="Time in bed" value={fmtMin(s.time_in_bed_min)} />
          <Stat label="Efficiency" value={s.efficiency_pct != null ? `${s.efficiency_pct}%` : "—"} />
          <Stat
            label="Wake time"
            value={fmtTime(s.final_wake_utc, s.timezone_name)}
            hint={s.timezone_name}
          />
        </div>
      )}

      <Card title="What happened">
        <p className="text-sm leading-relaxed">{c.what_happened}</p>
        {c.data_quality_reason && (
          <p className="mt-1 text-xs text-slate-500">{c.data_quality_reason}</p>
        )}
        {s && <div className="mt-2"><ConfidenceBadge level={s.confidence} /></div>}
      </Card>

      <Card title="What matters most" subtitle="Ranked for sleep hygiene and high performance">
        {([
          ["doing_well", "✓ Doing well", "text-emerald-300"],
          ["needs_improvement", "→ Needs improvement", "text-amber-300"],
          ["not_doing_well", "✗ Not doing well", "text-rose-300"],
        ] as const).map(([key, label, color]) => {
          const items = c.what_matters_most?.[key] ?? [];
          if (items.length === 0) return null;
          return (
            <div key={key} className="mb-3 last:mb-0">
              <h3 className={`mb-1 text-xs font-semibold uppercase tracking-wide ${color}`}>{label}</h3>
              <ul className="flex flex-col gap-2">
                {items.map((f: any, i: number) => (
                  <li key={i} className="flex items-start justify-between gap-3 text-sm">
                    <span>{f.finding}</span>
                    <ConfidenceBadge level={f.confidence} />
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </Card>

      <Card title="Likely contributors">
        <ul className="flex flex-col gap-2">
          {c.likely_contributors.map((f: any, i: number) => (
            <li key={i} className="text-sm">
              <div className="flex items-center justify-between gap-3">
                <span>{f.factor}</span>
                <ConfidenceBadge level={f.confidence} />
              </div>
              {f.note && <p className="text-xs text-slate-500">{f.note}</p>}
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Today's capacity" subtitle={c.todays_capacity.note}>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {["physical_recovery", "cognitive_energy", "stress_resilience", "sleepiness_risk", "training_readiness"].map(
            (k) => (
              <Stat key={k} label={k.replace(/_/g, " ")} value={c.todays_capacity[k]} />
            )
          )}
        </div>
        {c.todays_capacity.your_reported_morning_energy && (
          <p className="mt-2 text-xs text-slate-400">
            Your reported morning energy: {c.todays_capacity.your_reported_morning_energy}
          </p>
        )}
      </Card>

      <Card title="Today's actions">
        <ol className="list-decimal pl-5 text-sm leading-relaxed">
          {c.todays_actions.map((a: string, i: number) => (
            <li key={i}>{a}</li>
          ))}
        </ol>
      </Card>

      {t && (
        <Card title="Tonight's target" subtitle={t.formula}>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Wind-down" value={t.wind_down_start_local} />
            <Stat label="Lights out" value={`${t.lights_out_window_local[0]}–${t.lights_out_window_local[1]}`} />
            <Stat label="Target sleep" value={fmtMin(t.target_sleep_min)} />
            <Stat label="Wake window" value={`${t.recommended_wake_window_local[0]}–${t.recommended_wake_window_local[1]}`} />
          </div>
          {t.adjustments?.length > 0 && (
            <ul className="mt-2 list-disc pl-5 text-xs text-slate-400">
              {t.adjustments.map((a: string, i: number) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          )}
          <div className="mt-2"><ConfidenceBadge level={t.confidence} /></div>
        </Card>
      )}

      <Card title="One thing to learn">
        <p className="text-sm">{c.one_thing_to_learn}</p>
      </Card>

      <Disclaimer text={data.disclaimer} />
    </div>
  );
}
