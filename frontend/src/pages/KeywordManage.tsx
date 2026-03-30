import { useEffect, useState } from "react";
import { keywordsApi, articlesApi, Keyword, MentionItem } from "../api/client";

const DEFAULT_COLORS = ["#e74c3c", "#3498db", "#2ecc71", "#9b59b6", "#e67e22", "#1abc9c", "#f39c12", "#e91e63"];

export default function KeywordManage() {
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [name, setName] = useState("");
  const [aliases, setAliases] = useState("");
  const [color, setColor] = useState(DEFAULT_COLORS[0]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [mentions, setMentions] = useState<MentionItem[]>([]);
  const [loadingMentions, setLoadingMentions] = useState(false);

  const load = () => keywordsApi.list().then(setKeywords);
  useEffect(() => { load(); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const data = { name, aliases: aliases ? aliases.split(",").map((s) => s.trim()) : [], color };
    if (editingId) { await keywordsApi.update(editingId, data); }
    else { await keywordsApi.create(data); }
    setName(""); setAliases(""); setEditingId(null);
    setColor(DEFAULT_COLORS[keywords.length % DEFAULT_COLORS.length]);
    load();
  };

  const handleEdit = (kw: Keyword) => {
    setEditingId(kw.id); setName(kw.name); setAliases(kw.aliases.join(", ")); setColor(kw.color || DEFAULT_COLORS[0]);
  };

  const handleDelete = async (id: number) => {
    if (confirm("Delete this keyword?")) { await keywordsApi.delete(id); load(); }
  };

  const handleRescan = async (id: number) => {
    await keywordsApi.rescan(id); alert("Rescan started! Historical articles will be re-matched in the background.");
  };

  const handleViewArticles = async (id: number) => {
    if (expandedId === id) {
      setExpandedId(null);
      setMentions([]);
    } else {
      setLoadingMentions(true);
      setExpandedId(id);
      const data = await articlesApi.mentions(id);
      setMentions(data);
      setLoadingMentions(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1>Keyword Management</h1>
        <div className="page-desc">Add keywords and aliases to track across all data sources. Use "Rescan" after adding new aliases to match historical articles.</div>
      </div>

      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-title">{editingId ? "Edit Keyword" : "Add Keyword"}</div>
        <form onSubmit={handleSubmit} className="form-row">
          <input className="input" placeholder="Keyword name" value={name} onChange={(e) => setName(e.target.value)} required />
          <input className="input input-wide" placeholder="Aliases (comma separated)" value={aliases} onChange={(e) => setAliases(e.target.value)} />
          <input type="color" value={color} onChange={(e) => setColor(e.target.value)} style={{ height: 32, width: 40, border: "1px solid #ddd", borderRadius: 4, cursor: "pointer" }} />
          <button className="btn btn-primary" type="submit">{editingId ? "Update" : "Add"}</button>
          {editingId && <button className="btn" type="button" onClick={() => { setEditingId(null); setName(""); setAliases(""); }}>Cancel</button>}
        </form>
        <div className="help-text">Separate multiple aliases with commas, e.g. "AI Agent, AI Helper, AI assistant"</div>
      </div>

      {keywords.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="icon">&#128269;</div>
            <h3>No keywords yet</h3>
            <p>Add your first keyword above to start tracking concepts across tech news sources.</p>
          </div>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: 50 }}>Color</th>
                <th>Name</th>
                <th>Aliases</th>
                <th style={{ width: 280 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {keywords.map((kw) => (
                <>
                  <tr key={kw.id}>
                    <td><span style={{ display: "inline-block", width: 14, height: 14, borderRadius: "50%", background: kw.color || "#ccc" }} /></td>
                    <td style={{ fontWeight: 500 }}>{kw.name}</td>
                    <td style={{ color: "#888" }}>{kw.aliases.length > 0 ? kw.aliases.join(", ") : "-"}</td>
                    <td>
                      <div className="actions">
                        <button className={`btn btn-sm ${expandedId === kw.id ? "btn-primary" : ""}`} onClick={() => handleViewArticles(kw.id)}>
                          {expandedId === kw.id ? "Hide" : "Articles"}
                        </button>
                        <button className="btn btn-sm" onClick={() => handleEdit(kw)}>Edit</button>
                        <button className="btn btn-sm" onClick={() => handleRescan(kw.id)} title="Re-match against all historical articles">Rescan</button>
                        <button className="btn btn-sm btn-danger" onClick={() => handleDelete(kw.id)}>Delete</button>
                      </div>
                    </td>
                  </tr>
                  {expandedId === kw.id && (
                    <tr key={`${kw.id}-articles`}>
                      <td colSpan={4} className="articles-panel">
                        {loadingMentions ? (
                          <p className="loading loading-pulse">Loading articles...</p>
                        ) : mentions.length === 0 ? (
                          <p style={{ color: "#999", fontSize: 13 }}>No articles found for this keyword. Try adding data sources and running a crawl first.</p>
                        ) : (
                          <table className="sub-table">
                            <thead>
                              <tr>
                                <th>Source</th>
                                <th>Article</th>
                                <th>Match</th>
                                <th>Date</th>
                              </tr>
                            </thead>
                            <tbody>
                              {mentions.map((m) => (
                                <tr key={m.id}>
                                  <td><span className="badge badge-muted">{m.source_name}</span></td>
                                  <td>
                                    <a href={m.article_url} target="_blank" rel="noopener noreferrer">
                                      {m.article_title}
                                    </a>
                                  </td>
                                  <td><span className={`badge ${m.match_location === "title" ? "badge-success" : "badge-muted"}`}>{m.match_location}</span></td>
                                  <td style={{ whiteSpace: "nowrap", color: "#888" }}>{m.published_at?.split(" ")[0] || "-"}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
