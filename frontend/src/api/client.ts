import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000/api",
});

export interface Keyword {
  id: number;
  name: string;
  aliases: string[];
  color: string | null;
  is_active: boolean;
}

export interface DataSource {
  id: number;
  name: string;
  type: string;
  url: string;
  weight: number;
  enabled: boolean;
  status: string;
  last_fetched_at: string | null;
  last_error: string | null;
  consecutive_failures: number;
}

export interface TrendDataPoint {
  date: string;
  score: number;
  mention_count: number;
}

export interface HeatmapSeries {
  keyword: { id: number; name: string; color: string | null };
  data: TrendDataPoint[];
  trend: "rising" | "falling" | "stable";
}

export const keywordsApi = {
  list: () => api.get<Keyword[]>("/keywords").then((r) => r.data),
  create: (data: { name: string; aliases?: string[]; color?: string }) =>
    api.post<Keyword>("/keywords", data).then((r) => r.data),
  update: (id: number, data: Partial<Keyword>) =>
    api.put<Keyword>(`/keywords/${id}`, data).then((r) => r.data),
  delete: (id: number) => api.delete(`/keywords/${id}`),
  rescan: (id: number) =>
    api.post(`/keywords/${id}/rescan`).then((r) => r.data),
};

export const sourcesApi = {
  list: () => api.get<DataSource[]>("/sources").then((r) => r.data),
  create: (data: Partial<DataSource>) =>
    api.post<DataSource>("/sources", data).then((r) => r.data),
  update: (id: number, data: Partial<DataSource>) =>
    api.put<DataSource>(`/sources/${id}`, data).then((r) => r.data),
  delete: (id: number) => api.delete(`/sources/${id}`),
};

export const trendsApi = {
  heatmap: (period: string = "7d") =>
    api.get<HeatmapSeries[]>("/trends/heatmap", { params: { period } }).then((r) => r.data),
  hot: () => api.get("/trends/hot").then((r) => r.data),
  weekly: () => api.get("/summary/weekly").then((r) => r.data),
};

export const articlesApi = {
  list: (keyword_id?: number) =>
    api.get("/articles", { params: keyword_id ? { keyword_id } : {} }).then((r) => r.data),
  mentions: (keyword_id: number) =>
    api.get(`/keywords/${keyword_id}/mentions`).then((r) => r.data),
};

export const crawlApi = {
  trigger: () => api.post("/crawl/trigger").then((r) => r.data),
  status: () => api.get<{ status: string }>("/crawl/status").then((r) => r.data),
};
