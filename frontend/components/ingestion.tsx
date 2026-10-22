"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { AlertCircle, CheckCircle2, CloudUpload, FileSpreadsheet, LoaderCircle, Sparkles, X } from "lucide-react";
import type { Dataset, UploadResult } from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function IngestionStats({ datasets }: { datasets: Dataset[] }) {
  const raw = datasets.filter((dataset) => dataset.layer === "RAW");
  const totalRows = raw.reduce((sum, dataset) => sum + dataset.rows, 0);
  const avgQuality = raw.length ? Math.round(raw.reduce((sum, dataset) => sum + dataset.quality.score, 0) / raw.length) : 0;
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <Stat label="Files ingested" value={formatNumber(raw.length)} detail="In your RAW layer" />
      <Stat label="Total rows" value={formatNumber(totalRows)} detail="Ready for processing" />
      <Stat label="Average quality" value={`${avgQuality}%`} detail="Across uploaded data" />
    </div>
  );
}

function Stat({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <Card className="px-4 py-4"><p className="text-[11px] font-medium text-[#859089]">{label}</p><p className="mt-2 text-xl font-semibold tracking-tight text-[#24332c]">{value}</p><p className="mt-1 text-[10px] text-[#a0a9a3]">{detail}</p></Card>;
}

export function FileUpload({ onUpload }: { onUpload: (file: File) => Promise<UploadResult> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<UploadResult | null>(null);
  const onDrop = useCallback(async (files: File[]) => {
    if (!files.length) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await onUpload(files[0]));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Upload could not be completed.");
    } finally {
      setBusy(false);
    }
  }, [onUpload]);
  const { getRootProps, getInputProps, isDragActive, open, fileRejections } = useDropzone({
    onDrop, accept: { "text/csv": [".csv"], "application/vnd.ms-excel": [".csv"] },
    maxFiles: 1, maxSize: 15 * 1024 * 1024, noClick: true, noKeyboard: true,
  });
  const rejectionError = fileRejections[0]?.errors[0]?.message;
  return (
    <Card className="overflow-hidden">
      <CardHeader><div><CardTitle>Upload your data</CardTitle><p className="mt-1 text-xs text-[#8a9590]">Drop a CSV and let Data Sentient take it from here.</p></div><span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#eaf5ef] text-[#237b62]"><CloudUpload size={17} /></span></CardHeader>
      <CardContent>
        <div {...getRootProps()} className={`drop-zone ${isDragActive ? "drop-zone-active" : ""}`}>
          <input {...getInputProps()} />
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-[#32876a] shadow-sm"><CloudUpload size={22} /></span>
          <p className="mt-4 text-sm font-semibold text-[#314139]">{isDragActive ? "Drop your CSV here" : "Drag and drop your CSV here"}</p>
          <p className="mt-1.5 text-xs text-[#8b9690]">or browse files from your device</p>
          <Button className="mt-4" onClick={open} disabled={busy} type="button" variant="secondary" size="sm">Browse files</Button>
          <p className="mt-4 text-[10px] text-[#a0aaa4]">CSV files only · up to 15 MB</p>
        </div>
        {(error || rejectionError) && <div role="alert" className="mt-3 flex items-center gap-2 rounded-lg bg-[#fff2ee] px-3 py-2.5 text-xs text-[#b3533c]"><AlertCircle size={15} />{error || rejectionError}<button className="ml-auto" onClick={() => setError("")} aria-label="Dismiss error"><X size={14} /></button></div>}
        {busy && <div className="mt-4 flex items-center gap-3 rounded-lg border border-[#e9efeb] p-3"><LoaderCircle className="animate-spin text-[#32876a]" size={17} /><div><p className="text-xs font-semibold text-[#405047]">Analyzing your file</p><p className="mt-0.5 text-[10px] text-[#8e9992]">Inspecting schema, quality and sample rows…</p></div></div>}
        {result && <div className="mt-4 rounded-lg border border-[#dcebe2] bg-[#f8fbf9] p-4">
          <div className="flex items-center gap-2"><CheckCircle2 size={16} className="text-[#278064]" /><p className="text-xs font-semibold text-[#314139]">{result.dataset.filename} is ready</p><span className="ml-auto rounded-full bg-[#e6f3eb] px-2 py-1 text-[9px] font-semibold text-[#278064]">RAW</span></div>
          <p className="mt-2 text-[11px] text-[#77847c]">{formatNumber(result.dataset.rows)} rows · {result.dataset.columns} columns · {result.analysis.quality.score}% quality score</p>
          <div className="mt-3 flex items-start gap-2 border-t border-[#e8efea] pt-3"><Sparkles size={14} className="mt-0.5 shrink-0 text-[#ba8a37]" /><div><p className="text-[10px] leading-5 text-[#637168]">{result.analysis.recommendations.slice(0, 2).join(" ")}</p><p className="mt-1 text-[9px] text-[#9aa39e]">{result.analysis.mode === "ai" ? "AI recommendations based on schema and quality summary." : "Local schema and quality analysis."}</p>{result.analysis.warning && <p className="mt-1 text-[9px] text-[#b66a4d]">{result.analysis.warning}</p>}</div></div>
          <div className="mt-3 overflow-x-auto rounded-md border border-[#e9efeb] bg-white"><table className="data-table"><thead><tr>{result.dataset.schema.map((column) => <th key={column.name}>{column.name}</th>)}</tr></thead><tbody>{result.analysis.preview.slice(0, 2).map((row, index) => <tr key={index}>{result.dataset.schema.map((column) => <td key={column.name}>{String(row[column.name] ?? "—")}</td>)}</tr>)}</tbody></table></div>
        </div>}
      </CardContent>
    </Card>
  );
}

export function IngestionPage({ datasets, onUpload }: { datasets: Dataset[]; onUpload: (file: File) => Promise<UploadResult> }) {
  return <div className="page-stack">
    <div className="welcome-row"><div><div className="eyebrow">DATA OPERATIONS <span className="text-[#ccd3ce]">/</span> INGESTION</div><h1>Bring your data in<span className="text-[#27906e]">.</span></h1><p>Upload, inspect, and prepare data for your pipeline.</p></div><div className="hidden items-center gap-2 rounded-lg bg-[#eaf5ef] px-3 py-2 text-[10px] font-medium text-[#278064] sm:flex"><Sparkles size={14} /> Intelligent file analysis</div></div>
    <IngestionStats datasets={datasets} />
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.2fr_.8fr]"><FileUpload onUpload={onUpload} /><Card><CardHeader><div><CardTitle>How ingestion works</CardTitle><p className="mt-1 text-xs text-[#8a9590]">A clear path from file to insight.</p></div></CardHeader><CardContent className="space-y-4 pt-5">
      {[{ number: "01", title: "Upload a CSV", description: "Drop in your file. We’ll inspect the format and schema.", icon: CloudUpload }, { number: "02", title: "Review the analysis", description: "Get a quick read on columns, missing values and data quality.", icon: Sparkles }, { number: "03", title: "Process your data", description: "Promote clean data from RAW into your CURATED layer.", icon: FileSpreadsheet }].map(({ number, title, description, icon: Icon }) => <div className="flex gap-3" key={number}><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#f2f6f3] text-[#32876a]"><Icon size={15} /></span><div><div className="flex items-center gap-2"><span className="text-[9px] font-semibold text-[#a5afa9]">{number}</span><p className="text-xs font-semibold text-[#35453d]">{title}</p></div><p className="mt-1 text-[10px] leading-4 text-[#89948d]">{description}</p></div></div>)}
      <div className="rounded-lg bg-[#f6f8f6] p-3 text-[10px] leading-5 text-[#78857d]">Files are analyzed in your workspace. Snowflake delivery is available when configured by your administrator.</div>
    </CardContent></Card></div>
    <Card><CardHeader><div><CardTitle>Recent files</CardTitle><p className="mt-1 text-xs text-[#8a9590]">Data currently available in RAW and CURATED.</p></div></CardHeader><CardContent className="pt-4"><div className="overflow-x-auto"><table className="data-table"><thead><tr><th>File / table</th><th>Layer</th><th>Rows</th><th>Columns</th><th>Quality</th><th>Added</th></tr></thead><tbody>{datasets.map((dataset) => <tr key={dataset.name}><td><span className="flex items-center gap-2 font-medium text-[#34443c]"><FileSpreadsheet size={14} className="text-[#3a8a6c]" />{dataset.filename}</span><span className="ml-6 text-[9px] text-[#a0aaa4]">{dataset.name}</span></td><td><span className={`layer-chip ${dataset.layer === "CURATED" ? "layer-curated" : "layer-raw"}`}>{dataset.layer}</span></td><td>{formatNumber(dataset.rows)}</td><td>{dataset.columns}</td><td><span className="font-medium text-[#438368]">{dataset.quality.score}%</span></td><td>{new Date(dataset.created_at).toLocaleDateString()}</td></tr>)}{!datasets.length && <tr><td colSpan={6} className="py-8 text-center text-[#9aa39e]">No files ingested yet.</td></tr>}</tbody></table></div></CardContent></Card>
  </div>;
}
