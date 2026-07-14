"use client";

import { ReactNode } from "react";

export function Card({
  title,
  children,
  subtitle,
}: {
  title?: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-slate-700/60 bg-slate-900/60 p-4 shadow">
      {title && <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">{title}</h2>}
      {subtitle && <p className="mb-2 text-xs text-slate-500">{subtitle}</p>}
      {children}
    </section>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-lg bg-slate-800/60 p-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="text-xl font-semibold text-slate-100">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

const badgeColors: Record<string, string> = {
  high: "bg-emerald-900/70 text-emerald-300 border-emerald-700",
  moderate: "bg-amber-900/60 text-amber-300 border-amber-700",
  low: "bg-rose-900/60 text-rose-300 border-rose-700",
  insufficient_data: "bg-slate-800 text-slate-400 border-slate-600",
};

export function ConfidenceBadge({ level }: { level?: string | null }) {
  const key = level ?? "insufficient_data";
  return (
    <span
      className={`inline-block rounded-full border px-2 py-0.5 text-[11px] ${badgeColors[key] ?? badgeColors.insufficient_data}`}
      title="How much this value can be trusted given data coverage and source"
    >
      {key.replace("_", " ")} confidence
    </span>
  );
}

export function KindBadge({ kind }: { kind?: string }) {
  const labels: Record<string, string> = {
    measured: "measured",
    device_estimated: "device estimate",
    self_reported: "self-reported",
    system_derived: "derived",
    experimental: "experimental",
  };
  if (!kind) return null;
  return (
    <span className="inline-block rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">
      {labels[kind] ?? kind}
    </span>
  );
}

export function Disclaimer({ text }: { text?: string }) {
  return (
    <p className="mt-6 rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-xs leading-relaxed text-slate-500">
      {text ??
        "Educational and observational only. Consumer sleep trackers are not polysomnography; sleep-stage estimates can be inaccurate, HRV varies substantially between individuals, and snoring alone does not diagnose sleep apnea. Discuss persistent symptoms with a qualified healthcare professional."}
    </p>
  );
}

export function Empty({ message }: { message: string }) {
  return <div className="rounded-lg border border-dashed border-slate-700 p-6 text-center text-sm text-slate-500">{message}</div>;
}
