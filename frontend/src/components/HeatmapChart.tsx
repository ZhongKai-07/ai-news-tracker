import ReactECharts from "echarts-for-react";
import { HeatmapSeries } from "../api/client";

interface Props {
  data: HeatmapSeries[];
}

export default function HeatmapChart({ data }: Props) {
  if (!data.length) return <p>No data yet. Add keywords and trigger a crawl.</p>;

  const allDates = [...new Set(data.flatMap((s) => s.data.map((d) => d.date)))].sort();
  const keywords = data.map((s) => s.keyword.name);

  const heatmapData: number[][] = [];
  let maxScore = 0;
  data.forEach((series, kwIdx) => {
    series.data.forEach((point) => {
      const dateIdx = allDates.indexOf(point.date);
      heatmapData.push([dateIdx, kwIdx, point.score]);
      if (point.score > maxScore) maxScore = point.score;
    });
  });

  const option = {
    tooltip: {
      position: "top",
      formatter: (params: any) => {
        const [dateIdx, kwIdx, score] = params.data;
        const series = data[kwIdx];
        const point = series.data.find((d) => d.date === allDates[dateIdx]);
        return `${series.keyword.name}<br/>${allDates[dateIdx]}<br/>Score: ${score.toFixed(2)}<br/>Mentions: ${point?.mention_count || 0}`;
      },
    },
    grid: { top: 30, bottom: 60, left: 120, right: 30 },
    xAxis: { type: "category", data: allDates, splitArea: { show: true } },
    yAxis: { type: "category", data: keywords, splitArea: { show: true } },
    visualMap: {
      min: 0, max: maxScore || 1, calculable: true, orient: "horizontal", left: "center", bottom: 0,
      inRange: { color: ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"] },
    },
    series: [{ type: "heatmap", data: heatmapData, label: { show: false }, emphasis: { itemStyle: { shadowBlur: 10, shadowColor: "rgba(0,0,0,0.5)" } } }],
  };

  return <ReactECharts option={option} style={{ height: 200 + keywords.length * 40 }} />;
}
