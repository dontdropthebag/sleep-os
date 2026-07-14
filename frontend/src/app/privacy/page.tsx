"use client";

import { useEffect, useState } from "react";
import { API_BASE, apiGet } from "@/lib/api";
import { Card, Empty } from "@/components/ui";

export default function PrivacyPage() {
  const [audit, setAudit] = useState<any[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [confirmText, setConfirmText] = useState("");

  const load = () => apiGet("/api/privacy/audit").then(setAudit).catch(() => {});
  useEffect(() => { load(); }, []);

  async function exportAll() {
    const res = await fetch(`${API_BASE}/api/privacy/export`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sleep-os-export-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    load();
  }

  async function clinicianReport() {
    const data = await apiGet("/api/privacy/clinician-report");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "clinician-report.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function deleteAll() {
    if (confirmText !== "DELETE") {
      setMsg('Type DELETE in the box to confirm.');
      return;
    }
    const res = await fetch(`${API_BASE}/api/privacy/delete-all?confirm=DELETE`, { method: "POST" });
    const out = await res.json();
    setMsg(res.ok ? `All personal data deleted: ${JSON.stringify(out.deleted)}` : `Failed: ${JSON.stringify(out)}`);
    setConfirmText("");
    load();
  }

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-bold">Privacy & exports</h1>
        <p className="text-sm text-slate-400">
          All data lives in a local SQLite file on this machine. Nothing is uploaded anywhere, there
          are no trackers, and bedroom audio is never transcribed. Raw audio is discarded after
          analysis unless you explicitly enable retention.
        </p>
      </header>

      <Card title="Export">
        <div className="flex gap-3">
          <button onClick={exportAll}
                  className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500">
            Export all my data (JSON)
          </button>
          <button onClick={clinicianReport}
                  className="rounded-md bg-slate-700 px-4 py-2 text-sm font-medium text-white hover:bg-slate-600">
            Export for clinician
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          The clinician report summarises timing, regularity and snoring trends with data limitations.
          It contains no diagnoses.
        </p>
      </Card>

      <Card title="Delete everything" subtitle="Removes all sessions, raw records, habits, check-ins and profile. Irreversible.">
        <div className="flex items-center gap-3">
          <input value={confirmText} onChange={(e) => setConfirmText(e.target.value)}
                 placeholder='Type DELETE' aria-label="Deletion confirmation"
                 className="rounded-md border border-slate-700 bg-slate-800 px-2 py-1.5 text-sm text-slate-100" />
          <button onClick={deleteAll}
                  className="rounded-md bg-rose-700 px-4 py-2 text-sm font-medium text-white hover:bg-rose-600">
            Delete all personal data
          </button>
        </div>
        {msg && <p className="mt-2 text-sm text-amber-300">{msg}</p>}
      </Card>

      <Card title="Audit log" subtitle="Every import, edit, export and deletion is recorded locally.">
        {audit.length === 0 ? <Empty message="No audit entries." /> : (
          <ul className="flex max-h-80 flex-col gap-1 overflow-y-auto text-xs">
            {audit.map((a, i) => (
              <li key={i} className="flex justify-between border-t border-slate-800 py-1 first:border-0">
                <span className="font-medium text-slate-300">{a.action}</span>
                <span className="text-slate-500">{a.at?.slice(0, 19).replace("T", " ")}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
