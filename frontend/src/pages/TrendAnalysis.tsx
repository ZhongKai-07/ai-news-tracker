import { useEffect, useState } from "react";
import { trendsApi, keywordsApi, HeatmapSeries, Keyword } from "../api/client";
import HeatmapChart from "../components/HeatmapChart";
import TrendLineChart from "../components/TrendLineChart";
import KeywordSelector from "../components/KeywordSelector";

type ViewMode = "heatmap" | "line";

export default function TrendAnalysis() {
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [period, setPeriod] = useState("7d");
  const [viewMode, setViewMode] = useState<ViewMode>("heatmap");
  const [data, setData] = useState<HeatmapSeries[]>([]);

  useEffect(() => {
    keywordsApi.list().then((kws) => {
      setKeywords(kws);
      setSelected(kws.map((k) => k.id));
    });
  }, []);

  useEffect(() => {
    trendsApi.heatmap(period).then((all) => {
      const filtered = selected.length ? all.filter((s) => selected.includes(s.keyword.id)) : all;
      setData(filtered);
    });
  }, [period, selected]);

  return (
    <div>
      <h1>Trend Analysis</h1>
      <KeywordSelector keywords={keywords} selected={selected} onChange={setSelected} />
      <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
        {["7d", "30d", "90d"].map((p) => (
          <button key={p} onClick={() => setPeriod(p)}
            style={{ fontWeight: period === p ? "bold" : "normal", background: period === p ? "#3498db" : "#eee", color: period === p ? "white" : "black", border: "none", padding: "6px 16px", borderRadius: 4, cursor: "pointer" }}>
            {p}
          </button>
        ))}
        <span style={{ margin: "0 8px", color: "#ccc" }}>|</span>
        <button onClick={() => setViewMode("heatmap")}
          style={{ fontWeight: viewMode === "heatmap" ? "bold" : "normal", background: viewMode === "heatmap" ? "#2ecc71" : "#eee", color: viewMode === "heatmap" ? "white" : "black", border: "none", padding: "6px 16px", borderRadius: 4, cursor: "pointer" }}>
          Heatmap
        </button>
        <button onClick={() => setViewMode("line")}
          style={{ fontWeight: viewMode === "line" ? "bold" : "normal", background: viewMode === "line" ? "#2ecc71" : "#eee", color: viewMode === "line" ? "white" : "black", border: "none", padding: "6px 16px", borderRadius: 4, cursor: "pointer" }}>
          Trend Lines
        </button>
      </div>
      <div style={{ background: "white", padding: 16, borderRadius: 8 }}>
        {viewMode === "heatmap" ? <HeatmapChart data={data} /> : <TrendLineChart data={data} />}
      </div>
    </div>
  );
}
