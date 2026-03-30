import ReactECharts from "echarts-for-react";
import { HeatmapSeries } from "../api/client";

interface Props {
  data: HeatmapSeries[];
}

export default function TrendLineChart({ data }: Props) {
  if (!data.length) return <p>No data yet.</p>;

  const allDates = [...new Set(data.flatMap((s) => s.data.map((d) => d.date)))].sort();

  const series = data.map((s) => {
    const dateMap = new Map(s.data.map((d) => [d.date, d.score]));
    return {
      name: s.keyword.name,
      type: "line" as const,
      smooth: true,
      data: allDates.map((d) => dateMap.get(d) ?? 0),
      itemStyle: { color: s.keyword.color || undefined },
      lineStyle: { color: s.keyword.color || undefined },
    };
  });

  const option = {
    tooltip: { trigger: "axis" },
    legend: { data: data.map((s) => s.keyword.name) },
    grid: { top: 40, bottom: 30, left: 50, right: 30 },
    xAxis: { type: "category", data: allDates },
    yAxis: { type: "value", name: "Score" },
    series,
  };

  return <ReactECharts option={option} style={{ height: 400 }} />;
}
