"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { Card, ConfidenceBadge, Disclaimer, Empty } from "@/components/ui";

const LABELS: Record<string, string> = {
  earlier: "Earlier chronotype",
  intermediate: "Intermediate chronotype",
  later: "Later chronotype",
  insufficient_data: "Insufficient data",
  schedule_constrained: "Schedule-constrained pattern",
};

const EXPLANATIONS: Record<string, string> = {
  earlier:
    "You naturally fall asleep and wake earlier than most people. In practice: your sharpest " +
    "focus tends to come in the early-to-mid morning, evenings are for winding down, and late " +
    "nights cost you more than they cost others. Protect an early, consistent bedtime.",
  intermediate:
    "Your sleep timing sits in the typical middle range — neither strongly early nor late. In " +
    "practice: a consistent window around 23:00–07:00 suits you well, your strongest focus " +
    "usually lands mid-to-late morning, and you have decent flexibility either way as long as " +
    "you keep your wake time steady. Morning outdoor light keeps this rhythm anchored.",
  later:
    "You naturally fall asleep and wake later than most people. In practice: forcing very early " +
    "starts costs you more than it costs others, your best focus often comes later in the day, " +
    "and bright morning light plus dimmer evenings are your main tools for pulling your rhythm " +
    "earlier when your schedule demands it.",
  insufficient_data:
    "Not enough unconstrained nights yet to say. Keep importing data — free days without an " +
    "alarm are the most informative nights.",
  schedule_constrained:
    "Your schedule (alarms, travel) is masking your natural preference — the data shows what " +
    "your calendar demands, not what your body prefers. A few alarm-free mornings will reveal it.",
};

export default function ChronotypePage() {
  const [c, setC] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet("/api/metrics/chronotype").then(setC).catch((e) => setError(String(e)));
  }, []);

  if (error) return <Empty message={`Backend not reachable (${error}).`} />;
  if (!c) return <Empty message="Loading…" />;

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-bold">Chronotype & schedule</h1>
        <p className="text-sm text-slate-400">
          Estimated from your sleep timing on unconstrained free days — a behavioural estimate, not
          a measurement of circadian phase.
        </p>
      </header>

      <Card title="Estimate">
        <div className="flex items-center gap-3">
          <span className="text-xl font-semibold">{LABELS[c.category] ?? c.category}</span>
          <ConfidenceBadge level={c.confidence} />
        </div>
        {EXPLANATIONS[c.category] && (
          <p className="mt-2 rounded-lg bg-slate-800/50 p-3 text-sm leading-relaxed text-slate-300">
            {EXPLANATIONS[c.category]}
          </p>
        )}
        {c.corrected_midpoint_local && (
          <p className="mt-2 text-sm text-slate-300">
            Debt-corrected free-day sleep midpoint: <strong>{c.corrected_midpoint_local}</strong>{" "}
            (from {c.free_day_midpoint_nights} free nights, {c.nights_used} usable nights total).
          </p>
        )}
        {c.note && <p className="mt-2 text-sm text-slate-400">{c.note}</p>}
        {c.method && <p className="mt-2 text-xs text-slate-500">{c.method}</p>}
        {c.nights_required && (
          <p className="mt-2 text-sm text-amber-300/80">
            Needs at least {c.nights_required} usable nights (currently {c.nights_used}).
          </p>
        )}
      </Card>

      {c.excluded?.length > 0 && (
        <Card title="Excluded nights" subtitle="These nights were excluded so temporary disruption doesn't bias the estimate.">
          <ul className="flex flex-col gap-1 text-sm">
            {c.excluded.slice(0, 15).map((e: any, i: number) => (
              <li key={i} className="flex justify-between border-t border-slate-800 py-1 first:border-0">
                <span>{e.date}</span>
                <span className="text-xs text-slate-400">{e.reasons.join(", ")}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}
      <Disclaimer />
    </div>
  );
}
