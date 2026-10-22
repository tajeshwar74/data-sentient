"use client";

import { useState } from "react";
import { ArrowUpRight, Braces, CircleHelp, Clock3, LoaderCircle, Play, Sparkles, Table2, WandSparkles } from "lucide-react";
import type { Dataset, QueryResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const suggestions = [
  "How many rows are in this dataset?",
  "Show me a preview of the data",
  "What is the average revenue?",
];

export function QueryInput({ value, onChange, onSubmit, loading, table, tables, onTableChange }: {
  value: string; onChange: (value: string) => void; onSubmit: () => void; loading: boolean;
  table: string; tables: Dataset[]; onTableChange: (value: string) => void;
}) {
  return <Card>
    <CardHeader><div><CardTitle>Ask your data</CardTitle><p className="mt-1 text-xs text-[#8a9590]">Ask a question in plain language. We’ll shape it into a query.</p></div><span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#f0ebfa] text-[#8168b5]"><WandSparkles size={16} /></span></CardHeader>
    <CardContent className="pt-5">
      <label className="mb-2 block text-[10px] font-medium text-[#748078]" htmlFor="analytics-table">Data source</label>
      <select id="analytics-table" className="form-select mb-3 max-w-sm" value={table} onChange={(event) => onTableChange(event.target.value)}><option value="">Auto-select curated data</option>{tables.map((dataset) => <option key={dataset.name} value={dataset.name}>{dataset.layer} · {dataset.name}</option>)}</select>
      <textarea id="query-input" value={value} onChange={(event) => onChange(event.target.value)} onKeyDown={(event) => { if ((event.metaKey || event.ctrlKey) && event.key === "Enter") onSubmit(); }} rows={3} maxLength={1000} placeholder="e.g. What is the average revenue by region?" className="query-textarea" />
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3"><span className="text-[10px] text-[#9aa39e]">Be curious. Your data will answer.</span><Button onClick={onSubmit} disabled={loading || value.trim().length < 5}>{loading ? <LoaderCircle size={14} className="animate-spin" /> : <Play size={13} fill="currentColor" />} Generate insight</Button></div>
      <div className="mt-5 border-t border-[#eff2f0] pt-4"><p className="mb-2.5 text-[10px] font-medium text-[#849088]">Try asking</p><div className="flex flex-wrap gap-2">{suggestions.map((suggestion) => <button key={suggestion} onClick={() => onChange(suggestion)} className="rounded-full border border-[#e8ece9] bg-white px-3 py-1.5 text-[10px] text-[#6f7c74] transition-colors hover:border-[#afd1bf] hover:bg-[#f6faf7] hover:text-[#267a60]">{suggestion}</button>)}</div></div>
    </CardContent>
  </Card>;
}

export function SQLDisplay({ result }: { result: QueryResult }) {
  return <Card className="overflow-hidden">
    <CardHeader><div><CardTitle className="flex items-center gap-2"><Braces size={15} className="text-[#42866b]" />Generated SQL</CardTitle><p className="mt-1 text-xs text-[#8a9590]">A readable starting point for your analysis.</p></div><span className="rounded-md bg-[#f2f6f3] px-2 py-1 font-mono text-[9px] text-[#75827a]">SQL</span></CardHeader>
    <CardContent className="pt-4"><pre className="overflow-x-auto rounded-lg bg-[#182720] p-4 text-[11px] leading-6 text-[#d4e4d9]"><code>{result.sql}</code></pre><p className="mt-3 flex items-start gap-1.5 text-[10px] leading-4 text-[#939d97]"><CircleHelp size={13} className="mt-0.5 shrink-0" />{result.note}</p></CardContent>
  </Card>;
}

export function ResultsDisplay({ result }: { result: QueryResult }) {
  return <Card>
    <CardHeader><div><CardTitle>Query results</CardTitle><p className="mt-1 text-xs text-[#8a9590]">Showing {result.row_count} {result.row_count === 1 ? "row" : "rows"} from {result.table}.</p></div><span className="flex items-center gap-1 rounded-md bg-[#eaf5ef] px-2 py-1 text-[9px] font-medium text-[#278064]"><Clock3 size={11} /> Ready</span></CardHeader>
    <CardContent className="pt-4"><div className="overflow-x-auto rounded-lg border border-[#edf0ee]"><table className="data-table"><thead><tr>{result.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{result.rows.map((row, index) => <tr key={index}>{result.columns.map((column) => <td key={column}>{row[column] === null || row[column] === undefined ? "—" : String(row[column])}</td>)}</tr>)}{!result.rows.length && <tr><td colSpan={result.columns.length} className="py-8 text-center text-[#9aa39e]">No results to display.</td></tr>}</tbody></table></div></CardContent>
  </Card>;
}

export function AnalyticsPage({ datasets, onQuery }: { datasets: Dataset[]; onQuery: (question: string, table?: string) => Promise<QueryResult> }) {
  const [question, setQuestion] = useState("");
  const [table, setTable] = useState("");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const runQuery = async () => {
    if (question.trim().length < 5) return;
    setLoading(true);
    setError("");
    try { setResult(await onQuery(question, table || undefined)); } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not generate a query."); } finally { setLoading(false); }
  };
  return <div className="page-stack">
    <div className="welcome-row"><div><div className="eyebrow">DISCOVER <span className="text-[#ccd3ce]">/</span> AI ANALYTICS</div><h1>Talk to your data<span className="text-[#27906e]">.</span></h1><p>Turn a question into a useful first step, without writing SQL.</p></div><div className="hidden items-center gap-2 rounded-lg bg-[#f0ebfa] px-3 py-2 text-[10px] font-medium text-[#8168b5] sm:flex"><Sparkles size={14} /> Natural language analytics</div></div>
    <QueryInput value={question} onChange={setQuestion} onSubmit={runQuery} loading={loading} table={table} tables={datasets} onTableChange={setTable} />
    {error && <div role="alert" className="rounded-lg bg-[#fff2ee] px-4 py-3 text-xs text-[#b3533c]">{error}</div>}
    {result ? <div className="grid grid-cols-1 gap-4 xl:grid-cols-[.9fr_1.1fr]"><SQLDisplay result={result} /><ResultsDisplay result={result} /></div> : <Card className="border-dashed bg-[#fcfdfc]"><CardContent className="flex flex-col items-center py-10 text-center"><span className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#f0ebfa] text-[#8168b5]"><Table2 size={19} /></span><p className="mt-3 text-xs font-semibold text-[#536158]">Your answer will appear here</p><p className="mt-1 max-w-sm text-[10px] leading-5 text-[#929c96]">Choose a data source and ask a question. Results are based on tables already available in your workspace.</p><span className="mt-3 inline-flex items-center gap-1 text-[10px] text-[#9587b6]"><ArrowUpRight size={12} /> Start with a suggested question above.</span></CardContent></Card>}
  </div>;
}
