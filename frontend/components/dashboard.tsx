"use client";

import { formatDistanceToNow } from "date-fns";
import {
  Activity, ArrowDownRight, ArrowRight, ArrowUpRight, Check, CircleHelp,
  Clock3, Database, Ellipsis, FileCheck2, Layers3, RefreshCw, ShieldCheck,
  Sparkles, Workflow,
} from "lucide-react";
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { AuditEvent, DashboardData } from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function MetricCard({
  label, value, trend, detail, icon: Icon, tone = "green",
}: {
  label: string; value: string; trend: string; detail: string;
  icon: typeof Database; tone?: "green" | "blue" | "amber" | "purple";
}) {
  const tones = {
    green: "bg-[#eaf5ef] text-[#237b62]", blue: "bg-[#eaf1fb] text-[#4479b9]",
    amber: "bg-[#fbf1df] text-[#bd842a]", purple: "bg-[#f0ebfa] text-[#8168b5]",
  };
  return (
    <Card className="metric-card">
      <div className="flex items-start justify-between">
        <span className="text-[12px] font-medium text-[#75817b]">{label}</span>
        <span className={`flex h-9 w-9 items-center justify-center rounded-lg ${tones[tone]}`}><Icon size={17} /></span>
      </div>
      <div className="mt-4 flex items-baseline gap-2">
        <span className="text-[27px] font-semibold tracking-[-.055em] text-[#1b2923]">{value}</span>
        <span className="inline-flex items-center text-[11px] font-semibold text-[#268263]"><ArrowUpRight size={13} />{trend}</span>
      </div>
      <p className="mt-1 text-[11px] text-[#8a9590]">{detail}</p>
    </Card>
  );
}

export function PipelineStatus({ data }: { data: DashboardData | null }) {
  const storage = data?.storage === "snowflake" ? "Snowflake connected" : "Local workspace";
  return (
    <Card>
      <CardHeader><div><CardTitle>Pipeline status</CardTitle><p className="mt-1 text-xs text-[#8a9590]">Your data, moving in the right direction.</p></div>
        <button className="rounded-md p-1.5 text-[#9aa39e] hover:bg-[#f4f6f5]" aria-label="Pipeline options"><Ellipsis size={18} /></button></CardHeader>
      <CardContent className="pt-5">
        <div className="grid grid-cols-[1fr_34px_1fr_34px_1fr] items-center">
          <PipelineNode icon={Database} label="Ingestion" sub={`${data?.metrics.raw_tables ?? 0} RAW tables`} state="active" />
          <ArrowRight className="mx-auto text-[#c2cbc6]" size={17} />
          <PipelineNode icon={Sparkles} label="Processing" sub="Quality checks on" state="active" />
          <ArrowRight className="mx-auto text-[#c2cbc6]" size={17} />
          <PipelineNode icon={Layers3} label="Analytics" sub={`${data?.metrics.curated_tables ?? 0} CURATED tables`} state="ready" />
        </div>
        <div className="mt-5 flex items-center justify-between border-t border-[#eff2f0] pt-4 text-[11px]">
          <span className="flex items-center gap-1.5 text-[#718079]"><span className="live-dot" /> All systems operational</span>
          <span className="text-[#9aa39e]">{storage}</span>
        </div>
      </CardContent>
    </Card>
  );
}

function PipelineNode({ icon: Icon, label, sub, state }: { icon: typeof Database; label: string; sub: string; state: "active" | "ready" }) {
  return (
    <div className="flex flex-col items-center text-center">
      <div className={`relative flex h-11 w-11 items-center justify-center rounded-xl ${state === "active" ? "bg-[#eaf5ef] text-[#237b62]" : "bg-[#f0f3f1] text-[#65726c]"}`}>
        <Icon size={19} />
        <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full border-2 border-white bg-[#42a17e] text-white"><Check size={9} strokeWidth={3} /></span>
      </div>
      <span className="mt-2.5 text-[11px] font-semibold text-[#34443c]">{label}</span>
      <span className="mt-0.5 text-[9px] text-[#98a19c]">{sub}</span>
    </div>
  );
}

export function ActivityFeed({ events }: { events: AuditEvent[] }) {
  return (
    <Card>
      <CardHeader><div><CardTitle>Recent activity</CardTitle><p className="mt-1 text-xs text-[#8a9590]">The latest from your pipeline.</p></div>
        <Activity size={17} className="text-[#a2aca6]" /></CardHeader>
      <CardContent className="pt-2">
        <div className="divide-y divide-[#f0f2f1]">
          {events.length ? events.slice(0, 5).map((event) => (
            <div key={event.id} className="flex items-center gap-3 py-3">
              <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${event.status === "SUCCESS" ? "bg-[#eaf5ef] text-[#278064]" : "bg-[#fff1e9] text-[#ca7951]"}`}>
                {event.status === "SUCCESS" ? <FileCheck2 size={15} /> : <CircleHelp size={15} />}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[11px] font-medium text-[#34443c]">{event.filename}</p>
                <p className="mt-0.5 truncate text-[10px] text-[#929c96]">{event.details}</p>
              </div>
              <span className="shrink-0 text-[9px] text-[#9aa39e]">{formatDistanceToNow(new Date(event.timestamp), { addSuffix: true })}</span>
            </div>
          )) : (
            <div className="flex flex-col items-center py-8 text-center"><Clock3 size={20} className="text-[#b6c0ba]" /><p className="mt-2 text-xs font-medium text-[#69766f]">You’re all caught up</p><p className="mt-1 text-[10px] text-[#9aa39e]">Pipeline activity will show here.</p></div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function PipelineFlow({ data }: { data: DashboardData | null }) {
  return (
    <Card>
      <CardHeader><div><CardTitle>Data flow overview</CardTitle><p className="mt-1 text-xs text-[#8a9590]">Processed records · last 7 days</p></div>
        <div className="flex items-center gap-3 text-[10px] text-[#7b8780]"><span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full bg-[#238366]" /> RAW</span><span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full bg-[#a4cdbb]" /> CURATED</span></div></CardHeader>
      <CardContent className="h-[230px] pl-1 pt-5">
        <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={180}>
          <AreaChart data={data?.flow ?? []} margin={{ top: 4, right: 12, left: -20, bottom: 0 }}>
            <defs><linearGradient id="rawFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#238366" stopOpacity={0.15} /><stop offset="95%" stopColor="#238366" stopOpacity={0} /></linearGradient><linearGradient id="curatedFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#a4cdbb" stopOpacity={0.3} /><stop offset="95%" stopColor="#a4cdbb" stopOpacity={0} /></linearGradient></defs>
            <CartesianGrid vertical={false} stroke="#edf0ee" strokeDasharray="3 5" />
            <XAxis dataKey="day" tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: "#9aa39e" }} tickMargin={10} />
            <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: "#9aa39e" }} />
            <Tooltip contentStyle={{ border: "1px solid #e7ebe8", borderRadius: 9, fontSize: 11, boxShadow: "0 6px 18px #1e302411" }} />
            <Area type="monotone" dataKey="raw" name="RAW" stroke="#238366" strokeWidth={2} fill="url(#rawFill)" />
            <Area type="monotone" dataKey="curated" name="CURATED" stroke="#a4cdbb" strokeWidth={2} fill="url(#curatedFill)" />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export function Dashboard({ data }: { data: DashboardData | null }) {
  const metrics = data?.metrics;
  return (
    <div className="page-stack">
      <div className="welcome-row">
        <div><div className="eyebrow"><span className="live-dot" /> YOUR WORKSPACE</div><h1>Good morning<span className="text-[#27906e]">.</span></h1><p>Here’s what’s happening across your data today.</p></div>
        <div className="hidden items-center gap-2 rounded-lg border border-[#e7ebe8] bg-white px-3 py-2 text-[11px] text-[#718079] sm:flex"><RefreshCw size={13} /> Live overview <span className="text-[#c4ccc7]">·</span> Updated just now</div>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Rows processed" value={formatNumber(metrics?.rows_processed ?? 0)} trend="+12.8%" detail="Across all connected tables" icon={Database} tone="green" />
        <MetricCard label="Active pipelines" value={String(metrics?.active_pipelines ?? 0).padStart(2, "0")} trend="Healthy" detail="All scheduled jobs running" icon={Workflow} tone="blue" />
        <MetricCard label="Data quality score" value={`${metrics?.data_quality ?? 0}%`} trend="+2.4%" detail="Across available tables" icon={ShieldCheck} tone="amber" />
        <MetricCard label="Successful runs" value={metrics?.success_rate === null || metrics?.success_rate === undefined ? "—" : `${metrics.success_rate}%`} trend={metrics?.success_rate == null ? "No runs" : "On track"} detail="Recorded pipeline runs" icon={Activity} tone="purple" />
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.55fr_1fr]">
        <PipelineFlow data={data} />
        <PipelineStatus data={data} />
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.55fr_1fr]">
        <Card>
          <CardHeader><div><CardTitle>Pipeline health</CardTitle><p className="mt-1 text-xs text-[#8a9590]">A quick pulse check on your workflows.</p></div><span className="rounded-md bg-[#eaf5ef] px-2 py-1 text-[10px] font-medium text-[#278064]">All healthy</span></CardHeader>
          <CardContent className="grid grid-cols-1 gap-2 pt-4 sm:grid-cols-3">
            {[
              { name: "Ingestion pipeline", meta: "Runs every 15 minutes", icon: Database },
              { name: "Curation pipeline", meta: "Runs on new data", icon: Layers3 },
              { name: "Quality monitoring", meta: "Continuous checks", icon: ShieldCheck },
            ].map(({ name, meta, icon: Icon }) => <div key={name} className="flex items-center gap-3 rounded-lg border border-[#edf0ee] p-3"><span className="text-[#34856b]"><Icon size={16} /></span><div className="min-w-0 flex-1"><p className="truncate text-[11px] font-semibold text-[#405047]">{name}</p><p className="mt-1 truncate text-[9px] text-[#929c96]">{meta}</p></div><span className="live-dot" /></div>)}
          </CardContent>
        </Card>
        <ActivityFeed events={data?.activity ?? []} />
      </div>
      <p className="flex items-center justify-center gap-1.5 pb-2 text-[10px] text-[#a2aca6]"><ArrowDownRight size={12} /> Your data stays in your workspace.</p>
    </div>
  );
}
