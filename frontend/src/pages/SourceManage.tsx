import { useEffect, useState } from "react";
import { sourcesApi, crawlApi, DataSource } from "../api/client";

const SUGGESTED_SOURCES = [
  { name: "Hacker News", url: "https://hnrss.org/newest" },
  { name: "TechCrunch", url: "https://techcrunch.com/feed/" },
  { name: "OpenAI Blog", url: "https://openai.com/blog/rss.xml" },
  { name: "Anthropic Blog", url: "https://www.anthropic.com/rss.xml" },
];

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

  const handleQuickAdd = (s: { name: string; url: string }) => {
    setName(s.name);
    setUrl(s.url);
    setType("rss");
    setWeight("1.5");
  };

  const badgeClass = (s: string) =>
    s === "normal" ? "badge badge-success" : s === "error" ? "badge badge-error" : "badge badge-muted";

  return (
    <div>
      <div className="page-header">
        <h1>Source Management</h1>
        <div className="page-desc">Add RSS feeds or web scraper sources. The system auto-crawls every 6 hours, or click "Trigger Crawl" to fetch now.</div>
      </div>

      <div style={{ display: "flex", gap: 16, marginBottom: 24, alignItems: "flex-start" }}>
        <div className="card" style={{ flex: 1 }}>
          <div className="card-title">Add Source</div>
          <form onSubmit={handleSubmit} className="form-row">
            <input className="input" placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} required />
            <select className="select" value={type} onChange={(e) => setType(e.target.value)}>
              <option value="rss">RSS</option>
              <option value="web_scraper">Web Scraper</option>
              <option value="api">API</option>
            </select>
            <input className="input input-wide" placeholder="Feed URL" value={url} onChange={(e) => setUrl(e.target.value)} required />
            <input className="input" placeholder="Weight" value={weight} onChange={(e) => setWeight(e.target.value)} style={{ width: 60 }} />
            <button className="btn btn-primary" type="submit">Add</button>
          </form>
          <div className="help-text">Weight affects trend scoring. Higher weight = more influence (default: 1.0, major sources: 1.5-2.0)</div>
        </div>

        <button
          className={`btn ${crawlStatus === "running" ? "btn-success" : "btn-primary"}`}
          onClick={handleCrawl}
          disabled={crawlStatus === "running"}
          style={{ whiteSpace: "nowrap", minWidth: 140, justifyContent: "center" }}
        >
          {crawlStatus === "running" ? (
            <><span className="loading-pulse">&#9679;</span> Crawling...</>
          ) : (
            "Trigger Crawl"
          )}
        </button>
      </div>

      {sources.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="icon">&#128225;</div>
            <h3>No sources yet</h3>
            <p>Add RSS feeds to start collecting articles. Try one of these popular sources:</p>
          </div>
          <div style={{ maxWidth: 400, margin: "0 auto", paddingBottom: 16 }}>
            {SUGGESTED_SOURCES.map((s) => (
              <div key={s.url} className="suggested-source">
                <span style={{ fontWeight: 500 }}>{s.name}</span>
                <code>{s.url}</code>
                <button className="btn btn-sm" onClick={() => handleQuickAdd(s)}>Use</button>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Name</th>
                <th>Type</th>
                <th>URL</th>
                <th>Weight</th>
                <th>Last Fetched</th>
                <th>Failures</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => (
                <tr key={s.id}>
                  <td><span className={badgeClass(s.status)}>{s.status}</span></td>
                  <td style={{ fontWeight: 500 }}>{s.name}</td>
                  <td><span className="badge badge-muted">{s.type}</span></td>
                  <td style={{ maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={s.url}>{s.url}</td>
                  <td>{s.weight}</td>
                  <td style={{ color: "#888", whiteSpace: "nowrap" }}>{s.last_fetched_at ? new Date(s.last_fetched_at).toLocaleString() : "Never"}</td>
                  <td>{s.consecutive_failures > 0 ? <span className="badge badge-error">{s.consecutive_failures}</span> : "0"}</td>
                  <td><button className="btn btn-sm btn-danger" onClick={() => handleDelete(s.id)}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
