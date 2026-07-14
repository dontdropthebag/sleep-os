"use client";

import { useEffect, useState } from "react";
import { apiGet, apiSend } from "@/lib/api";
import { Card, Empty } from "@/components/ui";

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

export default function SettingsPage() {
  const [p, setP] = useState<any>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet("/api/profile").then(setP).catch((e) => setError(String(e)));
  }, []);

  if (error) return <Empty message={`Backend not reachable (${error}).`} />;
  if (!p) return <Empty message="Loading…" />;

  const set = (k: string, v: any) => setP((prev: any) => ({ ...prev, [k]: v }));

  async function save() {
    try {
      const { id: _id, ...body } = p;
      void _id;
      await apiSend("/api/profile", "PUT", body);
      setMsg("Profile saved.");
    } catch (e) {
      setMsg(`Save failed: ${e}`);
    }
  }

  const text = (k: string, label: string, type = "text") => (
    <label className="flex flex-col gap-1 text-xs text-slate-400">
      {label}
      <input type={type} value={p[k] ?? ""} aria-label={label}
             onChange={(e) => set(k, e.target.value === "" ? null : type === "number" ? Number(e.target.value) : e.target.value)}
             className="rounded-md border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-100" />
    </label>
  );

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-bold">Profile & settings</h1>
        <p className="text-sm text-slate-400">Everything here is editable; nothing is hard-coded into the algorithms.</p>
      </header>

      <Card title="About you">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {text("age_range", "Age range (e.g. 30-39)")}
          {text("sex", "Sex (optional)")}
          {text("height_cm", "Height (cm)", "number")}
          {text("weight_kg", "Weight (kg)", "number")}
          {text("occupation", "Occupation")}
          {text("travel_status", "Travel status")}
        </div>
      </Card>

      <Card title="Schedule">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {text("required_wake_time", "Required wake time (HH:MM)", "time")}
          {text("current_timezone", "Current timezone (IANA)")}
          {text("target_sleep_minutes", "Sleep target (min)", "number")}
        </div>
        <div className="mt-3">
          <span className="text-xs text-slate-400">Workdays</span>
          <div className="mt-1 flex gap-2">
            {DAYS.map((d) => {
              const active = (p.workdays ?? ["mon", "tue", "wed", "thu", "fri"]).includes(d);
              return (
                <button key={d} aria-pressed={active}
                        onClick={() => set("workdays", active
                          ? (p.workdays ?? []).filter((x: string) => x !== d)
                          : [...(p.workdays ?? []), d])}
                        className={`rounded-md px-2.5 py-1 text-xs ${active ? "bg-sky-600 text-white" : "bg-slate-800 text-slate-400"}`}>
                  {d}
                </button>
              );
            })}
          </div>
        </div>
      </Card>

      <Card title="Wellbeing guard"
            subtitle="If nightly numbers make you anxious, hide them and keep only weekly trends. Normal nights vary — that is not a problem to fix.">
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input type="checkbox" checked={p.hide_nightly_scores ?? false}
                 onChange={(e) => set("hide_nightly_scores", e.target.checked)} />
          Hide detailed nightly scores; show weekly trends only
        </label>
      </Card>

      <button onClick={save}
              className="w-fit rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500">
        Save profile
      </button>
      {msg && <p className="text-sm text-emerald-300">{msg}</p>}
    </div>
  );
}
