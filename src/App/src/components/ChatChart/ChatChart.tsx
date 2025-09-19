import React, { useEffect, useRef } from "react";
import {
  Chart as ChartJS,
  type ChartTypeRegistry,
  registerables,
} from "chart.js";
import { hideDataSetsLabelConfig } from "../../configs/Utils";

const chartTypes = {
  barChart: "bar",
  pieChart: "pie",
  doughNutChart: "doughnut",
  lineChart: "line",
};
interface ChartProps {
  chartContent: {
    data: any;
    options: any;
    type: string;
  };
}


const isValidChartConfig = (content: ChartProps["chartContent"]): boolean => {
  // Basic check for required fields
  if (!content || typeof content !== "object") return false;
  if (!content.data || !content.type) return false;
  // Chart.js expects data.datasets to be an array for most chart types
  if (
    ["bar", "line", "horizontalBar", "doughnut", "pie"].includes(content.type)
  ) {
    if (!content.data.datasets || !Array.isArray(content.data.datasets)) return false;
  }
  return true;
};

const ChatChart: React.FC<ChartProps> = ({ chartContent }) => {
  const chartRef = useRef<HTMLCanvasElement>(null);
  const validChart = isValidChartConfig(chartContent);

  useEffect(() => {
    if (validChart && chartRef.current && chartContent.data && chartContent?.type) {
      ChartJS.register(...registerables);

      const chartConfigData = {
        type:
          chartContent.type === "horizontalBar"
            ? chartTypes.barChart
            : (chartContent.type as keyof ChartTypeRegistry),
        data: { ...chartContent.data },
        options: {
          ...chartContent?.options,
          responsive: false,
          indexAxis:
            chartContent.type === "horizontalBar"
              ? "y"
              : chartContent?.options?.indexAxis,
        },
      };
      if (
        [chartTypes.barChart, chartTypes.lineChart].includes(
          chartConfigData.type
        )
      ) {
        if (typeof chartConfigData.options.plugins === "object") {
          chartConfigData.options.plugins = {
            ...chartConfigData.options.plugins,
            legend: hideDataSetsLabelConfig,
          };
        } else if (!chartConfigData.options.plugins) {
          chartConfigData.options.plugins = {
            legend: hideDataSetsLabelConfig,
          };
        }
      }

      const myChart = new ChartJS(chartRef.current, chartConfigData);

      const resizeObserver = new ResizeObserver(() => {
        requestAnimationFrame(() => {
          if (chartRef.current && myChart) {
            myChart.resize();
            myChart.update();
          }
        });
      });

      if (chartRef?.current?.parentElement !== null) {
        resizeObserver.observe(chartRef.current.parentElement);
      }

      return () => {
        if (
          chartRef?.current !== null &&
          chartRef?.current?.parentElement !== null
        ) {
          resizeObserver.unobserve(chartRef?.current?.parentElement);
        }
        if (myChart.destroy) {
          myChart.destroy();
        }
      };
    }
  }, [chartContent.data, chartContent?.options, chartContent?.type, validChart]);

  return (
    <div style={{ maxHeight: 350 }}>
      {validChart ? (
        <canvas ref={chartRef} />
      ) : (
        <div style={{ padding: 16, color: "#b71c1c", background: "#fff3f3", borderRadius: 8 }}>
          <strong>Unable to render chart. Here is the raw response:</strong>
          <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-word", marginTop: 8 }}>
            {JSON.stringify(chartContent, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};

export default ChatChart;
