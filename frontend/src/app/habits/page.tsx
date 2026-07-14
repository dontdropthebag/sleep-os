"use client";

import { useEffect, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { Card, Empty } from "@/components/ui";

const today = () => new Date().toISOString().slice(0, 10);

export default function HabitsPage() {
  const [date, setDate] = useState(today());
  const [form, setForm] = useState<any>({});
  const [saved, setSaved] = useState<string | null>(null);
  const [recent, setRecent] = useState<any[]>([]);

  const load = () => apiGet("/api/habits?days=14").then(setRecent).catch(() => {});
  useEffect(() => { load(); }, []);

  const set = (k: string, v: any) => setForm((f: any) => ({ ...f, [k]: v === "" ? null : v }));

  async function save() {
    try {
      await apiSend("/api/habits", "POST", { date, ...form });
      setSaved(`Saved habits for ${date}.`);
      setForm({});
      load();
    } catch (e) {
      setSaved(`Save failed: ${e}`);
    }
  }

  const num = (k: string, label: string, step = 1) => (
    <label className="flex flex-col gap-1 text-xs text-slate-400">
      {label}
      <input type="number" step={step} value={form[k] ?? ""} aria-label={label}
             onChange={(e) => set(k, e.target.value === "" ? "" : Number(e.target.value))}
             className="rounded-md border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-100" />
    </label>
  );
  const time = (k: string, label: string) => (
    <label className="flex flex-col gap-1 text-xs text-slate-400">
      {label}
      <input type="time" value={form[k] ?? ""} aria-label={label}
             onChange={(e) => set(k, e.target.value)}
             className="rounded-md border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-100" />
    </label>
  );
  const sel = (k: string, label: string, opts: string[]) => (
    <label className="flex flex-col gap-1 text-xs text-slate-400">
      {label}
      <select value={form[k] ?? ""} aria-label={label} onChange={(e) => set(k, e.target.value)}
              className="rounded-md border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-100">
        <option value="">—</option>
        {opts.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
  const bool = (k: string, label: string) => (
    <label className="flex items-center gap-2 text-sm text-slate-300">
      <input type="checkbox" checked={form[k] ?? false} onChange={(e) => set(k, e.target.checked)} />
      {label}
    </label>
  );

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-bold">Daily habits</h1>
        <p className="text-sm text-slate-400">
          Tag behaviours so the app can compare tagged vs untagged nights. Everything is optional and self-reported.
        </p>
      </header>

      <Card title="Is this worth doing?" subtitle="Short answer: yes, but only a few fields — 20 seconds a day.">
        <p className="text-sm leading-relaxed text-slate-300">
          You don&apos;t need to fill everything. The five tags with the biggest payoff for your data are:
        </p>
        <ol className="mt-2 list-decimal pl-5 text-sm leading-relaxed text-slate-300">
          <li><strong>Last caffeine time</strong> — late caffeine is the most common hidden sleep disruptor.</li>
          <li><strong>Alcohol units</strong> — the single strongest predictor of fragmented sleep and snoring.</li>
          <li><strong>Final meal time</strong> — late heavy meals push sleep onset later.</li>
          <li><strong>Sleeping position</strong> — lets the snoring dashboard test back- vs side-sleeping.</li>
          <li><strong>Travel / illness</strong> — so disrupted nights don&apos;t pollute your baselines.</li>
        </ol>
        <p className="mt-2 text-xs text-slate-500">
          After ~2 weeks of tags, the app can start comparing tagged vs untagged nights (e.g. &quot;alcohol
          nights vs not&quot;) with honest sample sizes. Without tags it can only describe your sleep, not
          explain it.
        </p>
      </Card>

      <Card title="Log habits">
        <label className="mb-3 flex w-48 flex-col gap-1 text-xs text-slate-400">
          Date
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
                 className="rounded-md border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-100" />
        </label>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {num("caffeine_mg", "Caffeine (mg)", 10)}
          {time("first_caffeine_time", "First caffeine")}
          {time("last_caffeine_time", "Last caffeine")}
          {num("alcohol_units", "Alcohol (units)", 0.5)}
          {time("last_alcohol_time", "Last alcohol")}
          {time("last_meal_time", "Final meal")}
          {sel("meal_size", "Meal size", ["light", "moderate", "heavy"])}
          {sel("exercise_type", "Exercise", ["none", "strength", "cardio", "mixed"])}
          {sel("exercise_intensity", "Intensity", ["low", "moderate", "high"])}
          {time("exercise_end_time", "Exercise ended")}
          {time("morning_light_start", "Morning light start")}
          {num("morning_light_minutes", "Morning light (min)", 5)}
          {sel("evening_screens", "Evening screens", ["none", "light", "heavy"])}
          {num("nap_minutes", "Nap (min)", 5)}
          {sel("sleeping_position", "Sleeping position", ["back", "side", "front", "varies"])}
          {sel("bedroom_temp", "Bedroom temp", ["cold", "cool", "neutral", "warm", "hot"])}
        </div>
        <div className="mt-3 flex flex-wrap gap-4">
          {bool("wind_down_routine", "Wind-down routine")}
          {bool("illness", "Illness")}
          {bool("pain", "Pain")}
          {bool("travel", "Travel")}
          {bool("timezone_change", "Timezone change")}
          {bool("partner_in_room", "Partner in room")}
        </div>
        <button onClick={save}
                className="mt-4 rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500">
          Save habits
        </button>
        {saved && <p className="mt-2 text-sm text-emerald-300">{saved}</p>}
      </Card>

      <Card title="Recent entries">
        {recent.length === 0 ? <Empty message="No habit logs yet." /> : (
          <ul className="flex flex-col gap-1 text-sm">
            {recent.map((h) => (
              <li key={h.date} className="flex justify-between border-t border-slate-800 py-1.5 first:border-0">
                <span>{h.date}</span>
                <span className="text-xs text-slate-400">
                  {[h.caffeine_mg && `caffeine ${h.caffeine_mg}mg`, h.alcohol_units ? `alcohol ${h.alcohol_units}u` : null,
                    h.exercise_type && h.exercise_type !== "none" && h.exercise_type,
                    h.travel && "travel", h.illness && "illness"].filter(Boolean).join(" · ") || "logged"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
