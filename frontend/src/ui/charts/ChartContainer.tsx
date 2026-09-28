import type { ReactNode } from "react";
import { ResponsiveContainer } from "recharts";

export function ChartContainer({ ariaLabel, height = 260, children }: { ariaLabel: string; height?: number; children: ReactNode }) {
  return <div className="chart-frame" role="group" aria-label={ariaLabel}>
    <ResponsiveContainer width="100%" height={height}>{children}</ResponsiveContainer>
  </div>;
}
