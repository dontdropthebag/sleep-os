"use client";

import { useState } from "react";
import { apiSend } from "@/lib/api";
import { Card } from "@/components/ui";

const today = () => new Date().toISOString().slice(0, 10);

const MORNING = [
  ["sleep_quality", "Perceived sleep quality"],
  ["refreshed", "Refreshed on waking"],
  ["morning_energy", "Morning energy"],
  ["daytime_sleepiness", "Daytime sleepiness"],
  ["mood", "Mood"],
  ["soreness", "Soreness"],
] as const;

const LATER = [
  ["energy", "Energy"],
  ["focus", "Focus"],
  ["stress", "Stress"],
  ["mood", "Mood"],
  ["motivation", "Motivation"],
  ["mental_clarity", "Mental clarity"],
  ["physical_fatigue", "Physical fatigue"],
  ["afternoon_crash", "Afternoon crash severity"],
  ["workout_quality", "Workout quality"],
] as const;

export default function CheckinPage() {
  const [kind, setKind] = useState<"morning" | "midday" | "evening">("morning");
  const [date, setDate] = useState(today());
  const [vals, setVals] = useState<Record<string, number>>({});
  const [msg, setMsg] = useState<string | null>(null);

  const fields = kind === "morning" ? MORNING : LATER;

  async function save() {
    try {
      await apiSend("/api/checkins", "POST", { date, kind, ...vals });
      setMsg(`Saved ${kind} check-in for ${date}.`);
      setVals({});
    } catch (e) {
      setMsg(`Save failed: ${e}`);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-bold">Check-in</h1>
        <p className="text-sm text-slate-400">
          Quick 1–10 ratings. These teach the system what actually predicts your energy and focus.
        </p>
      </header>

      <Card>
        <div className="mb-4 flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1 text-xs text-slate-400">
            Date
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
                   className="rounded-md border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-100" />
          </label>
          <div className="flex gap-1" role="tablist" aria-label="Check-in type">
            {(["morning", "midday", "evening"] as const).map((k) => (
              <button key={k} role="tab" aria-selected={kind === k}
                      onClick={() => { setKind(k); setVals({}); }}
                      className={`rounded-md px-3 py-1.5 text-sm ${kind === k ? "bg-sky-600 text-white" : "bg-slate-800 text-slate-300"}`}>
                {k}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-4">
          {fields.map(([key, label]) => (
            <label key={key} className="flex flex-col gap-1 text-sm text-slate-300">
              <span className="flex justify-between">
                {label}
                <span className="font-semibold text-sky-300">{vals[key] ?? "—"}</span>
              </span>
              <input type="range" min={1} max={10} value={vals[key] ?? 5}
                     aria-label={`${label}, 1 to 10`}
                     onChange={(e) => setVals((v) => ({ ...v, [key]: Number(e.target.value) }))} />
            </label>
          ))}
        </div>

        <button onClick={save}
                className="mt-4 rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500">
          Save check-in
        </button>
        {msg && <p className="mt-2 text-sm text-emerald-300">{msg}</p>}
      </Card>
    </div>
  );
}
