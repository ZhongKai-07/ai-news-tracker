import { useEffect, useState } from "react";
import { trendsApi, HeatmapSeries } from "../api/client";
import HeatmapChart from "../components/HeatmapChart";

export default function Dashboard() {
  const [heatmapData, setHeatmapData] = useState<HeatmapSeries[]>([]);
  const [hotKeywords, setHotKeywords] = useState<any[]>([]);

  useEffect(() => {
    trendsApi.heatmap("7d").then(setHeatmapData);
    trendsApi.hot().then(setHotKeywords);
  }, []);

  const trendArrow = (trend: string) =>
    trend === "rising" ? "^" : trend === "falling" ? "v" : "-";

  return (
    <div>
      <h1>Dashboard</h1>
      <div style={{ display: "flex", gap: 12, marginBottom: 24, flexWrap: "wrap" }}>
        {heatmapData.map((series) => (
          <div key={series.keyword.id} style={{
            background: "white", padding: 16, borderRadius: 8, minWidth: 150,
            borderLeft: `4px solid ${series.keyword.color || "#ccc"}`,
          }}>
            <div style={{ fontWeight: "bold" }}>{series.keyword.name}</div>
            <div style={{ fontSize: 24 }}>
              {trendArrow(series.trend)}
              <span style={{ fontSize: 14, marginLeft: 8, color: "#666" }}>{series.trend}</span>
            </div>
          </div>
        ))}
      </div>

      {hotKeywords.length > 0 && (
        <div style={{ marginBottom: 24, padding: 12, background: "#fff3e0", borderRadius: 8 }}>
          <strong>Hot Topics: </strong>
          {hotKeywords.map((h: any) => (
            <span key={h.keyword.id} style={{ marginRight: 12, color: h.keyword.color }}>
              {h.keyword.name} ^
            </span>
          ))}
        </div>
      )}

      <div style={{ background: "white", padding: 16, borderRadius: 8 }}>
        <h3>Last 7 Days</h3>
        <HeatmapChart data={heatmapData} />
      </div>
    </div>
  );
}
