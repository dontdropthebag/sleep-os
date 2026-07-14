"use client";

import { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis,
} from "recharts";
import { apiGet, fmtDay, fmtDayLong, fmtMin, fmtTime } from "@/lib/api";
import { Card, ConfidenceBadge, Disclaimer, Empty, Stat } from "@/components/ui";

function localMinutes(iso: string | null, tz: string): number | null {
  if (!iso) return null;
  const d = new Date(iso);
  const parts = new Intl.DateTimeFormat("en-GB", {
    hour: "numeric", minute: "numeric", hourCycle: "h23", timeZone: tz,
  }).formatToParts(d);
  const h = Number(parts.find((p) => p.type === "hour")?.value ?? 0);
  const m = Number(parts.find((p) => p.type === "minute")?.value ?? 0);
  return h * 60 + m;
}

const tooltipStyle = { background: "#0f172a", border: "1px solid #334155" };

function TimingTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-md border border-slate-600 bg-slate-900 p-2 text-xs">
      <div className="font-semibold text-slate-200">{fmtDayLong(p.fullDate)}</div>
      <div className="text-amber-300">Bedtime: {p.bedLabel ?? "—"}</div>
      <div className="text-sky-300">Wake: {p.wakeLabel ?? "—"}</div>
      <div className="text-slate-400">{p.tz}</div>
    </div>
  );
}

export default function TrendsPage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet("/api/metrics/overview?days=28").then(setData).catch((e) => setError(String(e)));
  }, []);

  if (error) return <Empty message={`Backend not reachable (${error}).`} />;
  if (!data) return <Empty message="Loading…" />;

  const trend = data.trend.filter((t: any) => !t.is_nap);
  const durationData = trend.map((t: any) => ({
    fullDate: t.date,
    label: fmtDay(t.date),
    sleep: t.total_sleep_min != null ? +(t.total_sleep_min / 60).toFixed(2) : null,
    efficiency: t.efficiency_pct,
  }));
  const timingData = trend.map((t: any) => {
    let bed = localMinutes(t.onset_utc, t.timezone_name);
    if (bed != null && bed > 720) bed -= 1440;
    const wake = localMinutes(t.wake_utc, t.timezone_name);
    return {
      fullDate: t.date,
      label: fmtDay(t.date),
      bed: bed != null ? +(bed / 60).toFixed(2) : null,
      wake: wake != null ? +(wake / 60).toFixed(2) : null,
      bedLabel: fmtTime(t.onset_utc, t.timezone_name),
      wakeLabel: fmtTime(t.wake_utc, t.timezone_name),
      tz: t.timezone_name,
    };
  });

  const reg = data.regularity;
  const debt = data.debt_14d;
  const need = data.sleep_need;
  const axisTick = { fontSize: 10, fill: "#94a3b8" };

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-bold">Trends</h1>
        <p className="text-sm text-slate-400">Last 28 nights · trends matter more than single nights</p>
      </header>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Stat label="7-day avg sleep" value={fmtMin(data.duration.avg_7d_min)} />
        <Stat label="28-day avg sleep" value={fmtMin(data.duration.avg_28d_min)} />
        <Stat
          label="Sleep need"
          value={fmtMin(need.sleep_need_min)}
          hint={need.basis === "evidence_range_and_preference" ? "reference range + preference" : "personal estimate"}
        />
        <Stat
          label="Meeting your need"
          value={need.fulfillment_10 != null ? `${need.fulfillment_10}/10` : "—"}
          hint={need.fulfillment_note}
        />
        <Stat
          label="14-night sleep debt"
          value={debt.status === "ok" ? fmtMin(debt.net_debt_min) : "—"}
          hint={debt.note}
        />
      </div>

      <Card title="Sleep duration" subtitle="Hours asleep per night (device-estimated). Dashed line = current sleep-need estimate.">
        <div className="h-64" role="img"
             aria-label={`Sleep duration for the last ${durationData.length} nights. 7-day average ${fmtMin(data.duration.avg_7d_min)}.`}>
          <ResponsiveContainer>
            <BarChart data={durationData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="label" tick={axisTick} interval="preserveStartEnd" minTickGap={28} />
              <YAxis domain={[0, 10]} tick={axisTick} unit="h" />
              <Tooltip contentStyle={tooltipStyle}
                       labelFormatter={(_, p: any) => p?.[0] ? fmtDayLong(p[0].payload.fullDate) : ""} />
              <ReferenceLine y={need.sleep_need_min / 60} stroke="#38bdf8" strokeDasharray="4 4" />
              <Bar dataKey="sleep" fill="#38bdf8" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card title="Sleep efficiency" subtitle="Total sleep ÷ time in bed × 100">
        <div className="h-48" role="img" aria-label="Sleep efficiency trend line chart.">
          <ResponsiveContainer>
            <LineChart data={durationData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="label" tick={axisTick} interval="preserveStartEnd" minTickGap={28} />
              <YAxis domain={[60, 100]} tick={axisTick} unit="%" />
              <Tooltip contentStyle={tooltipStyle}
                       labelFormatter={(_, p: any) => p?.[0] ? fmtDayLong(p[0].payload.fullDate) : ""} />
              <Line type="monotone" dataKey="efficiency" stroke="#34d399" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card
        title="Bedtime & wake-time consistency"
        subtitle="Local clock time per night. Negative = before midnight. Hover any point for the exact times."
      >
        <div className="h-56" role="img" aria-label="Scatter chart of bedtimes and wake times by night.">
          <ResponsiveContainer>
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="label" type="category" tick={{ fontSize: 9, fill: "#94a3b8" }}
                     allowDuplicatedCategory={false} interval="preserveStartEnd" minTickGap={24} />
              <YAxis dataKey="bed" type="number" domain={[-4, 12]} tick={axisTick} unit="h" />
              <Tooltip content={<TimingTooltip />} />
              <Scatter data={timingData} dataKey="bed" fill="#fbbf24" name="bedtime" />
              <Scatter data={timingData} dataKey="wake" fill="#38bdf8" name="wake" />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
        {reg.status === "ok" ? (
          <p className="mt-2 text-sm text-slate-300">
            Wake time varied by ±{Math.round(reg.wake_sd_min)} min, bedtime by ±{Math.round(reg.onset_sd_min)} min.{" "}
            {reg.social_jetlag_min != null &&
              `Free-day midpoint is ${Math.abs(Math.round(reg.social_jetlag_min))} min ${reg.social_jetlag_min > 0 ? "later" : "earlier"} than workdays (social jetlag).`}
          </p>
        ) : (
          <p className="mt-2 text-sm text-slate-500">Not enough nights yet for regularity metrics.</p>
        )}
      </Card>

      <Card title="Workday vs free-day">
        <div className="grid grid-cols-2 gap-3">
          <Stat label="Workday avg" value={fmtMin(data.duration.workday_avg_min)} />
          <Stat label="Free-day avg" value={fmtMin(data.duration.freeday_avg_min)} />
        </div>
      </Card>

      <div className="flex items-center gap-2 text-xs text-slate-500">
        Sleep-need estimate: <ConfidenceBadge level={need.confidence} />
      </div>
      <Disclaimer text={data.disclaimer} />
    </div>
  );
}
