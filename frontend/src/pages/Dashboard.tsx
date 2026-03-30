import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { trendsApi, HeatmapSeries } from "../api/client";
import HeatmapChart from "../components/HeatmapChart";

export default function Dashboard() {
  const [heatmapData, setHeatmapData] = useState<HeatmapSeries[]>([]);
  const [hotKeywords, setHotKeywords] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      trendsApi.heatmap("7d").then(setHeatmapData),
      trendsApi.hot().then(setHotKeywords),
    ]).finally(() => setLoading(false));
  }, []);

  const trendArrow = (trend: string) =>
    trend === "rising" ? "\u2197" : trend === "falling" ? "\u2198" : "\u2192";

  const trendColor = (trend: string) =>
    trend === "rising" ? "#27ae60" : trend === "falling" ? "#e74c3c" : "#999";

  if (loading) {
    return (
      <div>
        <div className="page-header">
          <h1>Dashboard</h1>
        </div>
        <p className="loading loading-pulse">Loading trend data...</p>
      </div>
    );
  }

  if (heatmapData.length === 0) {
    return (
      <div>
        <div className="page-header">
          <h1>Dashboard</h1>
        </div>
        <div className="card">
          <div className="empty-state">
            <div className="icon">&#128640;</div>
            <h3>Welcome to AI News Tracker!</h3>
            <p>
              Get started in two steps:<br />
              1. Go to <Link to="/keywords">Keywords</Link> and add concepts you want to track (e.g. "AI Agent", "MCP")<br />
              2. Go to <Link to="/sources">Sources</Link> and add RSS feeds to crawl, then click "Trigger Crawl"
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
        <div className="page-desc">Overview of your tracked keyword trends from the last 7 days</div>
      </div>

      <div className="kw-cards">
        {heatmapData.map((series) => (
          <div key={series.keyword.id} className="kw-card" style={{ borderLeftColor: series.keyword.color || "#ccc" }}>
            <div className="name">{series.keyword.name}</div>
            <div className="trend" style={{ color: trendColor(series.trend) }}>
              {trendArrow(series.trend)}
              <span className="label">{series.trend}</span>
            </div>
          </div>
        ))}
      </div>

      {hotKeywords.length > 0 && (
        <div className="hot-topics">
          <span className="label">&#128293; Hot Topics</span>
          {hotKeywords.map((h: any) => (
            <span key={h.keyword.id} className="tag" style={{ color: h.keyword.color }}>
              {h.keyword.name} &#8599;
            </span>
          ))}
        </div>
      )}

      <div className="card">
        <h3>7-Day Heatmap</h3>
        <HeatmapChart data={heatmapData} />
      </div>
    </div>
  );
}
