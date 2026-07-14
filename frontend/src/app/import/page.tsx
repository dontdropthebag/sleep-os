"use client";

import { useEffect, useState } from "react";
import { apiGet, apiSend, apiUpload, fmtMin, fmtTime } from "@/lib/api";
import { Card, Empty } from "@/components/ui";

export default function ImportPage() {
  const [preview, setPreview] = useState<any>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [history, setHistory] = useState<any[]>([]);

  const loadHistory = () => apiGet("/api/imports").then(setHistory).catch(() => {});
  useEffect(() => { loadHistory(); }, []);

  async function onFile(file: File) {
    setBusy(true);
    setMessage(null);
    try {
      const p = await apiUpload("/api/imports/preview", file);
      setPreview(p);
      // Preselect everything that is not a likely duplicate
      setSelected(new Set(p.sessions
        .map((s: any, i: number) => (s.likely_duplicate_of.length === 0 ? i : -1))
        .filter((i: number) => i >= 0)));
    } catch (e) {
      setMessage(`Import failed: ${e}`);
    } finally {
      setBusy(false);
    }
  }

  async function commit() {
    if (!preview) return;
    setBusy(true);
    try {
      const r = await apiSend(`/api/imports/${preview.batch_id}/commit`, "POST", {
        include_indices: Array.from(selected),
      });
      setMessage(`Saved ${r.created_session_ids.length} session(s), skipped ${r.skipped.length}.`);
      setPreview(null);
      loadHistory();
    } catch (e) {
      setMessage(`Commit failed: ${e}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-bold">Data import</h1>
        <p className="text-sm text-slate-400">
          Sleep as Android ZIP/CSV or a generic sleep CSV (columns: start, end, …). Files are parsed
          locally; you preview every session before anything is saved.
        </p>
      </header>

      <Card title="Upload">
        <input
          type="file"
          accept=".zip,.csv,.json"
          aria-label="Choose an export file to import"
          disabled={busy}
          onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
          className="block w-full text-sm text-slate-300 file:mr-3 file:rounded-md file:border-0 file:bg-sky-600 file:px-4 file:py-2 file:text-white hover:file:bg-sky-500"
        />
        {busy && <p className="mt-2 text-sm text-slate-400">Working…</p>}
        {message && <p className="mt-2 text-sm text-amber-300">{message}</p>}
      </Card>

      {preview && (
        <Card
          title={`Preview — ${preview.sessions.length} session(s) from ${preview.source} (parser ${preview.parser_version})`}
          subtitle="Untick anything you don't want. Likely duplicates are unticked by default."
        >
          {preview.issues.length > 0 && (
            <ul className="mb-3 flex flex-col gap-1">
              {preview.issues.map((i: any, k: number) => (
                <li key={k} className={`text-xs ${i.severity === "error" ? "text-rose-400" : i.severity === "warning" ? "text-amber-300" : "text-slate-400"}`}>
                  [{i.severity}] {i.message}
                </li>
              ))}
            </ul>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-slate-400">
                <tr>
                  <th className="p-2"></th>
                  <th className="p-2">Night of</th>
                  <th className="p-2">In bed</th>
                  <th className="p-2">Wake</th>
                  <th className="p-2">Asleep</th>
                  <th className="p-2">TZ</th>
                  <th className="p-2">Type</th>
                  <th className="p-2">Missing</th>
                  <th className="p-2">Duplicate?</th>
                </tr>
              </thead>
              <tbody>
                {preview.sessions.map((s: any, i: number) => (
                  <tr key={i} className="border-t border-slate-800">
                    <td className="p-2">
                      <input
                        type="checkbox"
                        aria-label={`Include session of ${s.session_date}`}
                        checked={selected.has(i)}
                        onChange={(e) => {
                          const next = new Set(selected);
                          if (e.target.checked) next.add(i);
                          else next.delete(i);
                          setSelected(next);
                        }}
                      />
                    </td>
                    <td className="p-2">{s.session_date}</td>
                    <td className="p-2">{fmtTime(s.in_bed_utc, s.timezone_name)}</td>
                    <td className="p-2">{fmtTime(s.final_wake_utc, s.timezone_name)}</td>
                    <td className="p-2">{fmtMin(s.total_sleep_min)}</td>
                    <td className="p-2 text-xs">{s.timezone_name}</td>
                    <td className="p-2">{s.is_nap ? "nap" : "main"}</td>
                    <td className="p-2 text-xs text-slate-500">{(s.missing_metrics ?? []).join(", ") || "—"}</td>
                    <td className="p-2 text-xs">{s.likely_duplicate_of.length > 0 ? "⚠ likely duplicate" : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button
            onClick={commit}
            disabled={busy || selected.size === 0}
            className="mt-3 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-40"
          >
            Save {selected.size} session(s)
          </button>
        </Card>
      )}

      <Card title="Import history" subtitle="Every upload is tracked so you always know what data arrived when.">
        {history.length > 0 && (
          <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div className="rounded-lg bg-slate-800/60 p-3">
              <div className="text-xs text-slate-400">First import</div>
              <div className="text-sm font-semibold text-slate-100">
                {new Date(history[history.length - 1].imported_at).toLocaleString("en-AU", {
                  weekday: "short", day: "2-digit", month: "2-digit", year: "numeric",
                  hour: "2-digit", minute: "2-digit",
                })}
              </div>
            </div>
            <div className="rounded-lg bg-slate-800/60 p-3">
              <div className="text-xs text-slate-400">Latest import</div>
              <div className="text-sm font-semibold text-slate-100">
                {new Date(history[0].imported_at).toLocaleString("en-AU", {
                  weekday: "short", day: "2-digit", month: "2-digit", year: "numeric",
                  hour: "2-digit", minute: "2-digit",
                })}
              </div>
            </div>
            <div className="rounded-lg bg-slate-800/60 p-3">
              <div className="text-xs text-slate-400">Total imports</div>
              <div className="text-sm font-semibold text-slate-100">{history.length}</div>
            </div>
          </div>
        )}
        {history.length === 0 ? (
          <Empty message="No imports yet." />
        ) : (
          <ul className="flex flex-col gap-1 text-sm">
            {history.map((b) => (
              <li key={b.id} className="flex justify-between border-t border-slate-800 py-1.5 first:border-0">
                <span>{b.filename ?? b.source} <span className="text-xs text-slate-500">({b.source}, parser {b.parser_version})</span></span>
                <span className="text-xs text-slate-400">
                  {b.status} · {b.sessions_staged} sessions ·{" "}
                  {b.imported_at
                    ? new Date(b.imported_at).toLocaleString("en-AU", {
                        day: "2-digit", month: "2-digit", year: "numeric",
                        hour: "2-digit", minute: "2-digit",
                      })
                    : "—"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
