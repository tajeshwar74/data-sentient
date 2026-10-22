"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle, ArrowUpRight, Bell, ChevronDown, CircleHelp, Command,
  FileClock, FileInput, LayoutDashboard, LoaderCircle, Menu, Search,
  Settings2, Sparkles, Workflow, X,
} from "lucide-react";
import { AnalyticsPage } from "@/components/analytics";
import { AuditPage } from "@/components/audit";
import { Dashboard } from "@/components/dashboard";
import { IngestionPage } from "@/components/ingestion";
import { ProcessingPage } from "@/components/processing";
import { apiClient, type AuditEvent, type DashboardData, type Dataset, type ProcessingResult, type QueryResult, type UploadResult } from "@/lib/api";

type PageKey = "overview" | "ingestion" | "processing" | "analytics" | "audit";
const navigation: { id: PageKey; label: string; icon: typeof LayoutDashboard; group: string }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard, group: "WORKSPACE" },
  { id: "ingestion", label: "Data ingestion", icon: FileInput, group: "WORKSPACE" },
  { id: "processing", label: "Processing", icon: Workflow, group: "WORKSPACE" },
  { id: "analytics", label: "AI analytics", icon: Sparkles, group: "DISCOVER" },
  { id: "audit", label: "Audit log", icon: FileClock, group: "OBSERVABILITY" },
];
const pageTitles: Record<PageKey, string> = { overview: "Overview", ingestion: "Data ingestion", processing: "Processing", analytics: "AI analytics", audit: "Audit log" };

function Sidebar({ active, onNavigate, mobileOpen, onClose }: { active: PageKey; onNavigate: (page: PageKey) => void; mobileOpen: boolean; onClose: () => void }) {
  const groups = [...new Set(navigation.map((item) => item.group))];
  return <>
    {mobileOpen && <button className="sidebar-overlay lg:hidden" aria-label="Close menu" onClick={onClose} />}
    <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
      <div className="brand"><span className="brand-mark"><Sparkles size={18} /></span><div><span className="brand-name">Data Sentient</span><span className="brand-caption">DATA PIPELINES</span></div><button className="ml-auto rounded-md p-1 text-[#81948a] hover:bg-white/10 lg:hidden" onClick={onClose} aria-label="Close navigation"><X size={17} /></button></div>
      <button className="workspace-switch"><span className="workspace-avatar">A</span><span className="min-w-0 flex-1 text-left"><span className="block truncate text-[11px] font-medium text-[#e9f0ec]">Acme workspace</span><span className="mt-0.5 block text-[9px] text-[#80938a]">Free plan</span></span><ChevronDown size={14} className="text-[#80938a]" /></button>
      <nav className="sidebar-nav">{groups.map((group) => <div key={group} className="nav-group"><p className="nav-group-label">{group}</p>{navigation.filter((item) => item.group === group).map(({ id, label, icon: Icon }) => <button key={id} onClick={() => { onNavigate(id); onClose(); }} className={`nav-link ${active === id ? "nav-link-active" : ""}`}><Icon size={16} strokeWidth={active === id ? 2 : 1.8} /><span>{label}</span>{id === "analytics" && <span className="nav-new">AI</span>}</button>)}</div>)}</nav>
      <div className="sidebar-bottom"><div className="help-card"><div className="flex items-center gap-2"><span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#264638] text-[#a5d5bd]"><CircleHelp size={15} /></span><span className="text-[10px] font-medium text-[#d3ded8]">Need a hand?</span><ArrowUpRight size={12} className="ml-auto text-[#81948a]" /></div><p className="mt-2 text-[9px] leading-4 text-[#91a49a]">Explore the docs and get more from your data.</p><button className="mt-2 text-[9px] font-semibold text-[#a7d6be]">Visit help center</button></div><div className="sidebar-user"><span className="user-avatar">JD</span><span className="min-w-0 flex-1"><span className="block truncate text-[10px] font-medium text-[#e6ede9]">Jordan Davis</span><span className="mt-0.5 block truncate text-[9px] text-[#82948b]">jordan@acme.com</span></span><Settings2 size={15} className="text-[#879990]" /></div></div>
    </aside>
  </>;
}

export default function Home() {
  const [page, setPage] = useState<PageKey>("overview");
  const [data, setData] = useState<DashboardData | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [dashboard, tables, audit] = await Promise.all([apiClient.dashboard(), apiClient.datasets(), apiClient.audit()]);
      setData(dashboard);
      setDatasets(tables);
      setEvents(audit);
      setError("");
    } catch (caught) {
      const detail = caught instanceof Error ? caught.message : "Unable to connect to the API.";
      setError(`Could not reach the API bridge. Start FastAPI on port 8000. ${detail}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void refresh(), 0);
    const timer = window.setInterval(() => void refresh(), 30_000);
    return () => {
      window.clearTimeout(initialLoad);
      window.clearInterval(timer);
    };
  }, [refresh]);

  const upload = useCallback(async (file: File): Promise<UploadResult> => {
    const result = await apiClient.upload(file);
    await refresh();
    return result;
  }, [refresh]);
  const process = useCallback(async (table: string): Promise<ProcessingResult> => {
    const result = await apiClient.process(table);
    await refresh();
    return result;
  }, [refresh]);
  const query = useCallback((question: string, table?: string): Promise<QueryResult> => apiClient.query(question, table), []);

  const groups = [...new Set(navigation.map((item) => item.group))];
  return <div className="app-shell">
    <Sidebar active={page} onNavigate={setPage} mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
    <main className="main-shell">
      <header className="topbar">
        <div className="flex min-w-0 items-center gap-3"><button className="icon-button lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu size={18} /></button><span className="hidden text-[11px] text-[#9aa39e] sm:block">Workspace</span><span className="hidden text-[11px] text-[#c5ccc7] sm:block">/</span><span className="truncate text-[11px] font-medium text-[#4c5b53]">{pageTitles[page]}</span></div>
        <div className="flex items-center gap-2"><button className="top-search hidden sm:flex" onClick={() => setSearchOpen((open) => !open)}><Search size={13} /><span>Search anything…</span><kbd><Command size={9} /> K</kbd></button><button className="icon-button relative" aria-label="Notifications"><Bell size={16} /><i className="notification-dot" /></button><span className="top-divider" /><span className="hidden text-[10px] text-[#89948d] md:block">Help center</span><button className="flex h-7 w-7 items-center justify-center rounded-full bg-[#e6f1e9] text-[9px] font-semibold text-[#397858]">JD</button></div>
      </header>
      <div className="content-area">
        {error && <div role="alert" className="mb-4 flex items-start gap-2 rounded-lg border border-[#f1d9cf] bg-[#fff9f6] px-3 py-2.5 text-[11px] text-[#a95a41]"><AlertCircle size={15} className="mt-0.5 shrink-0" /><span className="flex-1">{error}</span><button aria-label="Retry connection" onClick={() => { setLoading(true); void refresh(); }} className="font-semibold underline">Retry</button></div>}
        {loading && !data ? <div className="flex min-h-[55vh] items-center justify-center gap-2 text-xs text-[#8a9590]"><LoaderCircle size={17} className="animate-spin text-[#32876a]" />Connecting to your workspace…</div> : <>
          {page === "overview" && <Dashboard data={data} />}
          {page === "ingestion" && <IngestionPage datasets={datasets} onUpload={upload} />}
          {page === "processing" && <ProcessingPage datasets={datasets} onProcess={process} />}
          {page === "analytics" && <AnalyticsPage datasets={datasets} onQuery={query} />}
          {page === "audit" && <AuditPage events={events} />}
        </>}
        <footer className="app-footer"><span>© 2026 Data Sentient</span><span className="flex items-center gap-1.5"><i className={`h-1.5 w-1.5 rounded-full ${error ? "bg-[#d4825f]" : "bg-[#49a27d]"}`} />{error ? "API disconnected" : data?.storage === "snowflake" ? "Snowflake connected" : "Local workspace"}<span className="mx-1 text-[#d4dad6]">·</span>v1.0.0</span></footer>
      </div>
    </main>
    {searchOpen && <div className="search-modal-backdrop" onClick={() => setSearchOpen(false)}><div role="dialog" aria-modal="true" aria-label="Search workspace" className="search-modal" onClick={(event) => event.stopPropagation()}><div className="flex items-center gap-2 border-b border-[#edf0ee] px-4"><Search size={16} className="text-[#96a19a]" /><input autoFocus placeholder="Search pages…" className="h-12 flex-1 bg-transparent text-sm outline-none" onChange={(event) => { const match = navigation.find((item) => item.label.toLowerCase().includes(event.target.value.toLowerCase())); if (match && event.target.value) setPage(match.id); }} /><button onClick={() => setSearchOpen(false)} className="text-[10px] text-[#a0aaa4]">ESC</button></div><div className="p-2">{groups.map((group) => <div key={group}><p className="px-2 pb-1 pt-2 text-[9px] font-semibold tracking-wider text-[#a0aaa4]">{group}</p>{navigation.filter((item) => item.group === group).map(({ id, label, icon: Icon }) => <button key={id} onClick={() => { setPage(id); setSearchOpen(false); }} className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-xs text-[#54635a] hover:bg-[#f2f6f3]"><Icon size={14} />{label}</button>)}</div>)}</div></div></div>}
  </div>;
}
