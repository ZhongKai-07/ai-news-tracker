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
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    keywordsApi.list().then((kws) => {
      setKeywords(kws);
      setSelected(kws.map((k) => k.id));
    });
  }, []);

  useEffect(() => {
    setLoading(true);
    trendsApi.heatmap(period).then((all) => {
      const filtered = selected.length ? all.filter((s) => selected.includes(s.keyword.id)) : all;
      setData(filtered);
    }).finally(() => setLoading(false));
  }, [period, selected]);

  return (
    <div>
      <div className="page-header">
        <h1>Trend Analysis</h1>
        <div className="page-desc">Compare keyword trends across different time periods. Select keywords and choose a view mode.</div>
      </div>

      <KeywordSelector keywords={keywords} selected={selected} onChange={setSelected} />

      <div className="controls-bar">
        <div className="btn-group">
          {["7d", "30d", "90d", "120d"].map((p) => (
            <button key={p} className={`btn ${period === p ? "active" : ""}`} onClick={() => setPeriod(p)}>
              {p}
            </button>
          ))}
        </div>

        <div className="divider" />

        <div className="btn-group btn-group-green">
          <button className={`btn ${viewMode === "heatmap" ? "active" : ""}`} onClick={() => setViewMode("heatmap")}>
            Heatmap
          </button>
          <button className={`btn ${viewMode === "line" ? "active" : ""}`} onClick={() => setViewMode("line")}>
            Trend Lines
          </button>
        </div>
      </div>

      <div className="card">
        {loading ? (
          <p className="loading loading-pulse">Loading trends...</p>
        ) : selected.length === 0 ? (
          <div className="empty-state">
            <p>Select at least one keyword above to view trends.</p>
          </div>
        ) : (
          viewMode === "heatmap" ? <HeatmapChart data={data} /> : <TrendLineChart data={data} />
        )}
      </div>
    </div>
  );
}
