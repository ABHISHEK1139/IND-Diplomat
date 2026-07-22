"use client";

import ReactECharts from "echarts-for-react";

interface Scenario {
  name: string;
  probability: number;
}

interface ForecastChartsProps {
  scenarios: Scenario[];
  timelineData?: Array<[string, number]>;
}

export default function ForecastCharts({ scenarios, timelineData }: ForecastChartsProps) {
  // Sort scenarios by probability descending
  const sorted = [...scenarios].sort((a, b) => b.probability - a.probability);
  
  const barOption = {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      backgroundColor: "rgba(22, 27, 46, 0.9)",
      borderColor: "#1E2642",
      textStyle: { color: "#F1F5F9" },
    },
    grid: { left: "3%", right: "4%", bottom: "3%", top: "10%", containLabel: true },
    xAxis: {
      type: "value",
      max: 100,
      splitLine: { lineStyle: { color: "#1E2642" } },
      axisLabel: { color: "#94A3B8" },
    },
    yAxis: {
      type: "category",
      data: sorted.map((s) => s.name).reverse(),
      axisLabel: { color: "#F1F5F9", fontWeight: "bold" },
      axisLine: { lineStyle: { color: "#1E2642" } },
    },
    series: [
      {
        type: "bar",
        data: sorted.map((s) => s.probability).reverse(),
        itemStyle: {
          color: {
            type: "linear",
            x: 0, y: 0, x2: 1, y2: 0,
            colorStops: [
              { offset: 0, color: "rgba(59, 130, 246, 0.4)" }, // Accent/40
              { offset: 1, color: "#3B82F6" }, // Accent
            ],
          },
          borderRadius: [0, 4, 4, 0],
        },
        label: {
          show: true,
          position: "right",
          formatter: "{c}%",
          color: "#F1F5F9",
          fontWeight: "bold",
        },
      },
    ],
  };

  const lineOption = {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(22, 27, 46, 0.9)",
      borderColor: "#1E2642",
      textStyle: { color: "#F1F5F9" },
    },
    grid: { left: "3%", right: "4%", bottom: "3%", top: "15%", containLabel: true },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: ["2024", "2026", "2028", "2030", "2032", "2035"],
      axisLabel: { color: "#94A3B8" },
      axisLine: { lineStyle: { color: "#1E2642" } },
    },
    yAxis: {
      type: "value",
      max: 100,
      splitLine: { lineStyle: { color: "#1E2642", type: "dashed" } },
      axisLabel: { color: "#94A3B8", formatter: "{value}%" },
    },
    series: [
      {
        name: "Probability",
        type: "line",
        smooth: true,
        data: timelineData?.map(d => d[1]) || [15, 25, 42, 60, 75, 85],
        symbolSize: 8,
        itemStyle: { color: "#10B981" }, // Success
        areaStyle: {
          color: {
            type: "linear",
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(16, 185, 129, 0.3)" },
              { offset: 1, color: "rgba(16, 185, 129, 0)" },
            ],
          },
        },
      },
    ],
  };

  return (
    <div className="space-y-6">
      <div>
        <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Scenario Probabilities</h4>
        <div className="h-[200px] w-full">
          <ReactECharts option={barOption} style={{ height: "100%", width: "100%" }} />
        </div>
      </div>
      <div>
        <h4 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-2">Confidence Projection to 2035</h4>
        <div className="h-[200px] w-full">
          <ReactECharts option={lineOption} style={{ height: "100%", width: "100%" }} />
        </div>
      </div>
    </div>
  );
}
