import { useEffect, useState } from "react";
import { keywordsApi, Keyword } from "../api/client";

const DEFAULT_COLORS = ["#e74c3c", "#3498db", "#2ecc71", "#9b59b6", "#e67e22", "#1abc9c", "#f39c12", "#e91e63"];

export default function KeywordManage() {
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [name, setName] = useState("");
  const [aliases, setAliases] = useState("");
  const [color, setColor] = useState(DEFAULT_COLORS[0]);
  const [editingId, setEditingId] = useState<number | null>(null);

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
    await keywordsApi.rescan(id); alert("Rescan started");
  };

  return (
    <div>
      <h1>Keyword Management</h1>
      <form onSubmit={handleSubmit} style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        <input placeholder="Keyword name" value={name} onChange={(e) => setName(e.target.value)} required />
        <input placeholder="Aliases (comma separated)" value={aliases} onChange={(e) => setAliases(e.target.value)} />
        <input type="color" value={color} onChange={(e) => setColor(e.target.value)} />
        <button type="submit">{editingId ? "Update" : "Add"}</button>
        {editingId && <button type="button" onClick={() => { setEditingId(null); setName(""); setAliases(""); }}>Cancel</button>}
      </form>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left", padding: 8 }}>Color</th>
            <th style={{ textAlign: "left", padding: 8 }}>Name</th>
            <th style={{ textAlign: "left", padding: 8 }}>Aliases</th>
            <th style={{ textAlign: "left", padding: 8 }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {keywords.map((kw) => (
            <tr key={kw.id} style={{ borderTop: "1px solid #ddd" }}>
              <td style={{ padding: 8 }}><span style={{ display: "inline-block", width: 16, height: 16, borderRadius: "50%", background: kw.color || "#ccc" }} /></td>
              <td style={{ padding: 8 }}>{kw.name}</td>
              <td style={{ padding: 8 }}>{kw.aliases.join(", ")}</td>
              <td style={{ padding: 8, display: "flex", gap: 8 }}>
                <button onClick={() => handleEdit(kw)}>Edit</button>
                <button onClick={() => handleRescan(kw.id)}>Rescan</button>
                <button onClick={() => handleDelete(kw.id)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
