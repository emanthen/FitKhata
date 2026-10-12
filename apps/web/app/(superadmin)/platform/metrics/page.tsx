"use client";

import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { getPlatformMetrics } from "@fitkhata/api-client";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Banknote, LineChart as LineChartIcon, TrendingDown, TrendingUp } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatTile } from "@/components/stat-tile";
import { formatNpr } from "@/lib/money";

export default function MetricsPage() {
  const t = useTranslations("admin");
  const query = useQuery({ queryKey: ["platform", "metrics"], queryFn: getPlatformMetrics });
  const data = query.data;
  const byStatus = Object.entries(data?.by_status ?? {}).map(([status, count]) => ({
    status,
    count,
  }));

  return (
    <div className="space-y-6">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <LineChartIcon size={18} strokeWidth={2} className="text-primary" />
        {t("platformMetricsTitle")}
      </h1>
      {query.isLoading ? (
        <Skeleton className="h-60 w-full rounded-xl" />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <StatTile
              label={t("platformMetricsMrrLabel")}
              icon={<Banknote size={16} strokeWidth={2} />}
              value={formatNpr(data?.mrr_npr ?? "0", { symbol: true })}
            />
            <StatTile
              label={t("platformMetricsChurnLabel")}
              icon={<TrendingDown size={16} strokeWidth={2} />}
              value={`${data?.churn_rate_pct ?? 0}%`}
            />
            <StatTile
              label={t("platformMetricsTrialConversionLabel")}
              icon={<TrendingUp size={16} strokeWidth={2} />}
              value={`${data?.trial_conversion_pct ?? 0}%`}
            />
          </div>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm text-muted-foreground">
                {t("platformMetricsSubsByStatus")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={byStatus}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="status" fontSize={11} stroke="var(--muted-foreground)" />
                  <YAxis fontSize={11} allowDecimals={false} stroke="var(--muted-foreground)" />
                  <Tooltip />
                  <Bar dataKey="count" fill="var(--chart-1)" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
