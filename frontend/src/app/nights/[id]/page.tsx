"use client";

import { use, useEffect, useState } from "react";
import { apiGet, fmtMin, fmtTime } from "@/lib/api";
import { Card, ConfidenceBadge, Disclaimer, Empty, KindBadge, Stat } from "@/components/ui";

export default function NightDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [s, setS] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet(`/api/sessions/${id}`).then(setS).catch((e) => setError(String(e)));
  }, [id]);

  if (error) return <Empty message={error} />;
  if (!s) return <Empty message="Loading…" />;

  const stg = s.stage_summary;
  const cont = s.continuity;

  return (
    <div className="flex flex-col gap-4">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Night of {s.session_date}</h1>
          <p className="text-sm text-slate-400">
            {s.source} · {s.timezone_name} · {s.is_nap ? "nap" : "main sleep"}
          </p>
        </div>
        <ConfidenceBadge level={s.confidence} />
      </header>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="In bed" value={fmtTime(s.in_bed_utc, s.timezone_name)} />
        <Stat label="Final wake" value={fmtTime(s.final_wake_utc, s.timezone_name)} />
        <Stat label="Time in bed" value={fmtMin(s.time_in_bed_min)} />
        <Stat label="Asleep (device est.)" value={fmtMin(s.total_sleep_min)} />
      </div>

      <Card title="Continuity">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Latency" value={cont.sleep_latency_min != null ? `${cont.sleep_latency_min} min` : "not recorded"} />
          <Stat label="WASO" value={cont.waso_min != null ? `${cont.waso_min} min` : "not recorded"} />
          <Stat label="Awakenings" value={cont.awakenings_count ?? "not recorded"} />
          <Stat label="Maintenance eff." value={cont.sleep_maintenance_efficiency_pct != null ? `${cont.sleep_maintenance_efficiency_pct}%` : "—"} />
        </div>
      </Card>

      {stg ? (
        <Card title="Sleep stages" subtitle={stg.note}>
          <div className="grid grid-cols-3 gap-3">
            {["deep", "rem", "light"].map((k) => (
              <Stat key={k} label={`${k} (device est.)`}
                    value={stg[`${k}_min`] != null ? fmtMin(stg[`${k}_min`]) : "—"}
                    hint={stg[`${k}_pct`] != null ? `${stg[`${k}_pct`]}% of sleep` : undefined} />
            ))}
          </div>
          <p className="mt-2 text-xs text-slate-500">{stg.transitions} stage transitions <KindBadge kind="device_estimated" /></p>
        </Card>
      ) : (
        <Card title="Sleep stages"><p className="text-sm text-slate-500">No stage data for this night — nothing is estimated in its place.</p></Card>
      )}

      {(s.snore_minutes != null || s.noise_level != null) && (
        <Card title="Snoring & noise">
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Snoring (device est.)" value={s.snore_minutes != null ? `${s.snore_minutes} min` : "—"} />
            <Stat label="Noise level" value={s.noise_level ?? "—"} />
          </div>
        </Card>
      )}

      <Card title="Provenance" subtitle="Where every metric came from">
        <table className="w-full text-left text-xs">
          <thead className="text-slate-500"><tr><th className="p-1.5">Field</th><th className="p-1.5">Original field</th><th className="p-1.5">Kind</th><th className="p-1.5">Confidence</th></tr></thead>
          <tbody>
            {Object.entries(s.field_provenance ?? {})
              .filter(([k]) => k !== "_missing_metrics")
              .map(([k, v]: [string, any]) => (
                <tr key={k} className="border-t border-slate-800">
                  <td className="p-1.5">{k}</td>
                  <td className="p-1.5 text-slate-400">{v.original_field}</td>
                  <td className="p-1.5"><KindBadge kind={v.kind} /></td>
                  <td className="p-1.5">{v.confidence}</td>
                </tr>
              ))}
          </tbody>
        </table>
        {s.field_provenance?._missing_metrics && (
          <p className="mt-2 text-xs text-amber-300/80">
            Not available from this source: {s.field_provenance._missing_metrics.join(", ")}
          </p>
        )}
      </Card>

      {s.quality_breakdown && (
        <Card title="Data-quality score" subtitle={`Overall: ${s.data_quality_score}/100 — this scores the data, not your sleep.`}>
          <ul className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs sm:grid-cols-3">
            {Object.entries(s.quality_breakdown).map(([k, v]: [string, any]) => (
              <li key={k} className="flex justify-between border-b border-slate-800/60 py-1">
                <span className="text-slate-400">{k.replace(/_/g, " ")}</span>
                <span>{v.value}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {s.comments && <Card title="Comments & tags"><p className="text-sm">{s.comments}</p></Card>}
      <Disclaimer />
    </div>
  );
}
