import { Keyword } from "../api/client";

interface Props {
  keywords: Keyword[];
  selected: number[];
  onChange: (ids: number[]) => void;
}

export default function KeywordSelector({ keywords, selected, onChange }: Props) {
  const toggle = (id: number) => {
    if (selected.includes(id)) {
      onChange(selected.filter((x) => x !== id));
    } else {
      onChange([...selected, id]);
    }
  };

  const selectAll = () => onChange(keywords.map((k) => k.id));
  const clearAll = () => onChange([]);

  return (
    <div className="card" style={{ marginBottom: 16, padding: "12px 16px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <span className="card-title" style={{ margin: 0 }}>Keywords</span>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-sm" onClick={selectAll}>Select All</button>
          <button className="btn btn-sm" onClick={clearAll}>Clear</button>
        </div>
      </div>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        {keywords.map((kw) => (
          <label key={kw.id} style={{ display: "flex", alignItems: "center", gap: 5, cursor: "pointer", fontSize: 13 }}>
            <input type="checkbox" checked={selected.includes(kw.id)} onChange={() => toggle(kw.id)} />
            <span style={{ width: 10, height: 10, borderRadius: "50%", background: kw.color || "#ccc", display: "inline-block" }} />
            {kw.name}
          </label>
        ))}
      </div>
    </div>
  );
}
