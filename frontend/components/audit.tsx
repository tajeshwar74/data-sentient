"use client";

import { useMemo, useState } from "react";
import { Download, FileSearch, Search, SlidersHorizontal } from "lucide-react";
import type { AuditEvent } from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function AuditFilters({ search, onSearch, status, onStatus }: {
  search: string; onSearch: (value: string) => void; status: string; onStatus: (value: string) => void;
}) {
  return <div className="flex flex-col gap-2 sm:flex-row">
    <label className="relative min-w-0 flex-1"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9aa39e]" /><input value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Search files, tables or details…" className="form-input pl-9" /></label>
    <label className="relative sm:w-44"><SlidersHorizontal size={13} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#9aa39e]" /><select className="form-select pl-9" value={status} onChange={(event) => onStatus(event.target.value)}><option>All statuses</option><option>SUCCESS</option><option>FAILED</option></select></label>
  </div>;
}

export function AuditTable({ events }: { events: AuditEvent[] }) {
  const exportCsv = () => {
    const columns = ["timestamp", "filename", "table", "status", "rows", "details"];
    const quote = (value: unknown) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const csv = [columns.join(","), ...events.map((event) => columns.map((column) => quote(event[column as keyof AuditEvent])).join(","))].join("\n");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    link.download = "data-sentient-audit.csv";
    link.click();
    URL.revokeObjectURL(link.href);
  };
  return <Card><CardHeader><div><CardTitle>Audit trail</CardTitle><p className="mt-1 text-xs text-[#8a9590]">An at-a-glance record of pipeline activity.</p></div><Button variant="secondary" size="sm" onClick={exportCsv} disabled={!events.length}><Download size={13} /> Export CSV</Button></CardHeader>
    <CardContent className="pt-4"><div className="overflow-x-auto"><table className="data-table"><thead><tr><th>Timestamp</th><th>File</th><th>Target table</th><th>Rows</th><th>Status</th><th>Details</th></tr></thead><tbody>{events.map((event) => <tr key={event.id}><td className="whitespace-nowrap">{new Date(event.timestamp).toLocaleString()}</td><td className="font-medium text-[#435149]">{event.filename}</td><td><span className="font-mono text-[10px]">{event.table}</span></td><td>{formatNumber(event.rows)}</td><td><span className={`status-chip ${event.status === "SUCCESS" ? "status-success" : "status-failed"}`}><i />{event.status}</span></td><td className="min-w-[180px]">{event.details}</td></tr>)}{!events.length && <tr><td colSpan={6} className="py-12 text-center"><div className="flex flex-col items-center text-[#9aa39e]"><FileSearch size={22} /><p className="mt-2 text-xs font-medium">No matching audit events</p><p className="mt-1 text-[10px]">Try adjusting your filters or upload a CSV.</p></div></td></tr>}</tbody></table></div></CardContent></Card>;
}

export function AuditPage({ events }: { events: AuditEvent[] }) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("All statuses");
  const filtered = useMemo(() => events.filter((event) => {
    const matchesStatus = status === "All statuses" || event.status === status;
    const haystack = `${event.filename} ${event.table} ${event.details}`.toLowerCase();
    return matchesStatus && haystack.includes(search.toLowerCase());
  }), [events, search, status]);
  return <div className="page-stack">
    <div className="welcome-row"><div><div className="eyebrow">OBSERVABILITY <span className="text-[#ccd3ce]">/</span> AUDIT LOG</div><h1>Know what happened<span className="text-[#27906e]">.</span></h1><p>Every file, every run, all in one place.</p></div><div className="hidden rounded-lg border border-[#e7ebe8] bg-white px-3 py-2 text-[10px] text-[#78847d] sm:block">{events.length} events recorded</div></div>
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3"><Card className="p-4"><p className="text-[10px] text-[#89948d]">Total events</p><p className="mt-2 text-xl font-semibold text-[#34443c]">{formatNumber(events.length)}</p></Card><Card className="p-4"><p className="text-[10px] text-[#89948d]">Successful runs</p><p className="mt-2 text-xl font-semibold text-[#278064]">{formatNumber(events.filter((event) => event.status === "SUCCESS").length)}</p></Card><Card className="p-4"><p className="text-[10px] text-[#89948d]">Rows affected</p><p className="mt-2 text-xl font-semibold text-[#34443c]">{formatNumber(events.reduce((sum, event) => sum + event.rows, 0))}</p></Card></div>
    <Card><CardContent className="pt-5"><div className="mb-4 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wide text-[#89948d]"><SlidersHorizontal size={13} /> Filter events</div><AuditFilters search={search} onSearch={setSearch} status={status} onStatus={setStatus} /></CardContent></Card>
    <AuditTable events={filtered} />
  </div>;
}
