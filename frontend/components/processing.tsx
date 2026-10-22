"use client";

import { useState } from "react";
import { ArrowRight, CheckCircle2, CircleHelp, Database, LoaderCircle, Play, ShieldCheck, Sparkles } from "lucide-react";
import type { Dataset, ProcessingResult } from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function TableSelector({ datasets, value, onChange }: { datasets: Dataset[]; value: string; onChange: (table: string) => void }) {
  const rawDatasets = datasets.filter((dataset) => dataset.layer === "RAW");
  return <label className="block"><span className="mb-2 block text-[11px] font-medium text-[#647169]">Select a RAW table</span><select className="form-select" value={value} onChange={(event) => onChange(event.target.value)}><option value="">Choose a table…</option>{rawDatasets.map((dataset) => <option key={dataset.name} value={dataset.name}>{dataset.name} · {formatNumber(dataset.rows)} rows</option>)}</select>{!rawDatasets.length && <span className="mt-2 block text-[10px] text-[#a1aaa5]">Upload a CSV first to get started.</span>}</label>;
}

export function ProcessingResults({ result }: { result: ProcessingResult }) {
  return <div className="space-y-4">
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {[["Rows processed", formatNumber(result.rows_processed)], ["Rows curated", formatNumber(result.rows_output)], ["Duplicates removed", formatNumber(result.duplicates_removed)], ["Quality score", `${result.quality.score}%`]].map(([label, value]) => <div key={label} className="rounded-lg border border-[#edf0ee] p-3"><p className="text-[10px] text-[#89948d]">{label}</p><p className="mt-1.5 text-base font-semibold text-[#34443c]">{value}</p></div>)}
    </div>
    <div className="rounded-lg bg-[#f7faf8] p-3"><p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-[#75827a]">Normalized schema</p><div className="flex flex-wrap gap-1.5">{result.schema.map((column) => <span key={column.name} className="rounded-md border border-[#e7ece8] bg-white px-2 py-1 text-[9px] text-[#647169]">{column.name}<span className="ml-1 text-[#a4ada7]">{column.type}</span></span>)}</div></div>
    <div className="overflow-x-auto rounded-lg border border-[#edf0ee]"><table className="data-table"><thead><tr>{Object.keys(result.preview[0] ?? {}).map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{result.preview.slice(0, 5).map((row, index) => <tr key={index}>{Object.keys(result.preview[0] ?? {}).map((column) => <td key={column}>{String(row[column] ?? "—")}</td>)}</tr>)}</tbody></table></div>
  </div>;
}

export function ProcessingPage({ datasets, onProcess }: { datasets: Dataset[]; onProcess: (table: string) => Promise<ProcessingResult> }) {
  const [table, setTable] = useState("");
  const [result, setResult] = useState<ProcessingResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async () => {
    if (!table) return;
    setBusy(true);
    setError("");
    try { setResult(await onProcess(table)); } catch (caught) { setError(caught instanceof Error ? caught.message : "Processing failed."); } finally { setBusy(false); }
  };
  return <div className="page-stack">
    <div className="welcome-row"><div><div className="eyebrow">DATA OPERATIONS <span className="text-[#ccd3ce]">/</span> PROCESSING</div><h1>Make data useful<span className="text-[#27906e]">.</span></h1><p>Transform raw tables into clean, trusted data.</p></div><div className="hidden items-center gap-2 rounded-lg bg-[#eaf5ef] px-3 py-2 text-[10px] font-medium text-[#278064] sm:flex"><ShieldCheck size={14} /> Quality checks enabled</div></div>
    <Card><CardHeader><div><CardTitle>RAW → CURATED transformation</CardTitle><p className="mt-1 text-xs text-[#8a9590]">Choose a source table to normalize and validate.</p></div><span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#f0ebfa] text-[#8168b5]"><Sparkles size={16} /></span></CardHeader><CardContent className="pt-5">
      <div className="grid grid-cols-1 items-end gap-4 md:grid-cols-[1fr_auto_1fr_auto]"><div className="rounded-lg border border-[#e8ece9] bg-[#fbfcfb] p-3"><span className="layer-chip layer-raw">RAW</span><div className="mt-3"><TableSelector datasets={datasets} value={table} onChange={(value) => { setTable(value); setResult(null); }} /></div></div><ArrowRight className="hidden justify-self-center text-[#9daa9f] md:block" size={18} /><div className="rounded-lg border border-[#dcebe2] bg-[#f8fbf9] p-3"><span className="layer-chip layer-curated">CURATED</span><p className="mt-4 text-[11px] font-medium text-[#5c6b62]">Clean, analytics-ready tables</p><p className="mt-1 text-[10px] text-[#929d96]">Standardized schema · quality checked</p></div><Button onClick={run} disabled={!table || busy} className="md:mb-0.5">{busy ? <LoaderCircle className="animate-spin" size={15} /> : <Play size={14} fill="currentColor" />} Run processing</Button></div>
      <div className="mt-5 grid grid-cols-1 gap-2 border-t border-[#eff2f0] pt-4 sm:grid-cols-3">{["Standardize column names", "Remove duplicate records", "Measure data quality"].map((action) => <div key={action} className="flex items-center gap-2 text-[10px] text-[#6f7d74]"><CheckCircle2 size={14} className="text-[#389070]" />{action}</div>)}</div>
      {error && <div role="alert" className="mt-4 flex items-center gap-2 rounded-lg bg-[#fff2ee] px-3 py-2.5 text-xs text-[#b3533c]"><CircleHelp size={14} />{error}</div>}
    </CardContent></Card>
    {result && <Card><CardHeader><div><CardTitle>Processing complete</CardTitle><p className="mt-1 text-xs text-[#8a9590]">{result.source_table} has been promoted to {result.table}.</p></div><span className="rounded-full bg-[#e6f3eb] px-2.5 py-1 text-[9px] font-semibold text-[#278064]">SUCCESS</span></CardHeader><CardContent className="pt-5"><ProcessingResults result={result} /></CardContent></Card>}
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">{[{ title: "Schema normalization", description: "Consistent, SQL-ready column names.", icon: Database }, { title: "Duplicate handling", description: "Repeated rows identified and removed.", icon: CheckCircle2 }, { title: "Quality scoring", description: "Nulls and duplicates summarized.", icon: ShieldCheck }].map(({ title, description, icon: Icon }) => <Card key={title} className="p-4"><Icon size={17} className="text-[#438a70]" /><p className="mt-3 text-xs font-semibold text-[#435149]">{title}</p><p className="mt-1 text-[10px] text-[#929c96]">{description}</p></Card>)}</div>
  </div>;
}
