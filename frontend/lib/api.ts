import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  timeout: 30_000,
});

api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error)) {
      const detail: unknown = error.response?.data?.detail;
      if (typeof detail === "string") return Promise.reject(new Error(detail));
      return Promise.reject(new Error(error.message));
    }
    return Promise.reject(error);
  },
);

export type Dataset = {
  name: string;
  filename: string;
  layer: "RAW" | "CURATED";
  rows: number;
  columns: number;
  created_at: string;
  quality: { score: number; missing_values: number; duplicate_rows: number; columns: number; rows: number };
  schema: { name: string; type: string }[];
};

export type AuditEvent = {
  id: string;
  timestamp: string;
  filename: string;
  table: string;
  status: string;
  rows: number;
  details: string;
};

export type DashboardData = {
  metrics: {
    rows_processed: number;
    active_pipelines: number;
    data_quality: number;
    success_rate: number | null;
    raw_tables: number;
    curated_tables: number;
  };
  datasets: Dataset[];
  activity: AuditEvent[];
  flow: { day: string; raw: number; curated: number }[];
  storage: string;
  updated_at: string;
};

export type UploadResult = {
  dataset: Dataset;
  analysis: {
    quality: Dataset["quality"];
    preview: Record<string, unknown>[];
    recommendations: string[];
    mode: "ai" | "local";
    warning: string | null;
  };
  storage: string;
};

export type ProcessingResult = {
  source_table: string;
  table: string;
  rows_processed: number;
  rows_output: number;
  duplicates_removed: number;
  quality: Dataset["quality"];
  schema: Dataset["schema"];
  preview: Record<string, unknown>[];
  storage: string;
};

export type QueryResult = {
  question: string;
  sql: string;
  table: string;
  row_count: number;
  columns: string[];
  rows: Record<string, unknown>[];
  summary: string;
  summary_mode: "ai" | "local";
  summary_note: string | null;
  note: string;
};

export const apiClient = {
  dashboard: () => api.get<DashboardData>("/api/dashboard").then((response) => response.data),
  datasets: () => api.get<Dataset[]>("/api/datasets").then((response) => response.data),
  audit: () => api.get<AuditEvent[]>("/api/audit").then((response) => response.data),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post<UploadResult>("/api/ingest", form).then((response) => response.data);
  },
  process: (table: string) =>
    api.post<ProcessingResult>(`/api/process/${encodeURIComponent(table)}`).then((response) => response.data),
  query: (question: string, table?: string) =>
    api.post<QueryResult>("/api/query", { question, table }).then((response) => response.data),
};
