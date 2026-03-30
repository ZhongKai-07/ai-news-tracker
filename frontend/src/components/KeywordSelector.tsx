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

  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
      {keywords.map((kw) => (
        <label key={kw.id} style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
          <input type="checkbox" checked={selected.includes(kw.id)} onChange={() => toggle(kw.id)} />
          <span style={{ width: 12, height: 12, borderRadius: "50%", background: kw.color || "#ccc", display: "inline-block" }} />
          {kw.name}
        </label>
      ))}
    </div>
  );
}
