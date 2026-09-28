import { useState } from "react";
import { api } from "../../lib/api";
import type { DashboardRange } from "../../contracts/api";
import { DataNotice, LoadingLine, ModelUsagePanel, PageHeader, useLoad } from "../shared";
import { DashboardAnalyticsPanel } from "../DashboardAnalyticsPanel";

export function DeveloperAnalyticsPage() {
  const [range, setRange] = useState<DashboardRange>("current_month");
  const data = useLoad(() => api.getDeveloperDashboard(range), [range]);

  return <>
    <PageHeader title="Analytics" description="Requests, tokens, and known spend for the selected window." />
    <DataNotice error={data.error} onRetry={data.reload} developer />
    {data.loading && <LoadingLine />}
    <DashboardAnalyticsPanel analytics={data.value?.analytics ?? null} range={range} onRangeChange={setRange} loading={data.loading} />
    <ModelUsagePanel models={data.value?.topModels ?? []} loading={data.loading} developer />
  </>;
}
