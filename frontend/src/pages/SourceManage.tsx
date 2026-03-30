import { useEffect, useState } from "react";
import { sourcesApi, crawlApi, DataSource } from "../api/client";

export default function SourceManage() {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [name, setName] = useState("");
  const [type, setType] = useState("rss");
  const [url, setUrl] = useState("");
  const [weight, setWeight] = useState("1.0");
  const [crawlStatus, setCrawlStatus] = useState("idle");

  const load = () => sourcesApi.list().then(setSources);
  useEffect(() => { load(); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await sourcesApi.create({ name, type, url, weight: parseFloat(weight) });
    setName(""); setUrl(""); setWeight("1.0");
    load();
  };

  const handleDelete = async (id: number) => {
    if (confirm("Delete this source?")) { await sourcesApi.delete(id); load(); }
  };

  const handleCrawl = async () => {
    try {
      await crawlApi.trigger();
      setCrawlStatus("running");
      const poll = setInterval(async () => {
        const s = await crawlApi.status();
        setCrawlStatus(s.status);
        if (s.status === "idle") { clearInterval(poll); load(); }
      }, 2000);
    } catch { alert("Crawl already running"); }
  };

  const statusColor = (s: string) => s === "normal" ? "#2ecc71" : s === "error" ? "#e74c3c" : "#95a5a6";

  return (
    <div>
      <h1>Source Management</h1>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <form onSubmit={handleSubmit} style={{ display: "flex", gap: 8 }}>
          <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} required />
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="rss">RSS</option>
            <option value="web_scraper">Web Scraper</option>
            <option value="api">API</option>
          </select>
          <input placeholder="URL" value={url} onChange={(e) => setUrl(e.target.value)} required style={{ width: 300 }} />
          <input placeholder="Weight" value={weight} onChange={(e) => setWeight(e.target.value)} style={{ width: 60 }} />
          <button type="submit">Add Source</button>
        </form>
        <button onClick={handleCrawl} disabled={crawlStatus === "running"}>
          {crawlStatus === "running" ? "Crawling..." : "Trigger Crawl"}
        </button>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left", padding: 8 }}>Status</th>
            <th style={{ textAlign: "left", padding: 8 }}>Name</th>
            <th style={{ textAlign: "left", padding: 8 }}>Type</th>
            <th style={{ textAlign: "left", padding: 8 }}>URL</th>
            <th style={{ textAlign: "left", padding: 8 }}>Weight</th>
            <th style={{ textAlign: "left", padding: 8 }}>Last Fetched</th>
            <th style={{ textAlign: "left", padding: 8 }}>Failures</th>
            <th style={{ textAlign: "left", padding: 8 }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {sources.map((s) => (
            <tr key={s.id} style={{ borderTop: "1px solid #ddd" }}>
              <td style={{ padding: 8 }}><span style={{ color: statusColor(s.status), fontWeight: "bold" }}>{s.status}</span></td>
              <td style={{ padding: 8 }}>{s.name}</td>
              <td style={{ padding: 8 }}>{s.type}</td>
              <td style={{ padding: 8, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis" }}>{s.url}</td>
              <td style={{ padding: 8 }}>{s.weight}</td>
              <td style={{ padding: 8 }}>{s.last_fetched_at || "Never"}</td>
              <td style={{ padding: 8 }}>{s.consecutive_failures}</td>
              <td style={{ padding: 8 }}><button onClick={() => handleDelete(s.id)}>Delete</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
