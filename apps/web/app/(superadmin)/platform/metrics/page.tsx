"use client";

import { useQuery } from "@tanstack/react-query";
import { getPlatformMetrics } from "@fitkhata/api-client";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatNpr } from "@/lib/money";

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border p-4">
      <p className="text-sm opacity-70">{label}</p>
      <p className="text-2xl font-semibold">{value}</p>
    </div>
  );
}

export default function MetricsPage() {
  const query = useQuery({ queryKey: ["platform", "metrics"], queryFn: getPlatformMetrics });
  const data = query.data;
  const byStatus = Object.entries(data?.by_status ?? {}).map(([status, count]) => ({
    status,
    count,
  }));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Metrics</h1>
      {query.isLoading ? (
        <p className="text-sm opacity-60">Loading...</p>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatTile label="MRR" value={formatNpr(data?.mrr_npr ?? "0", { symbol: true })} />
            <StatTile label="Churn rate" value={`${data?.churn_rate_pct ?? 0}%`} />
            <StatTile
              label="Trial conversion"
              value={`${data?.trial_conversion_pct ?? 0}%`}
            />
          </div>
          <div className="rounded border p-4">
            <h2 className="mb-3 text-sm font-medium opacity-70">Subscriptions by status</h2>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={byStatus}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="status" fontSize={11} />
                <YAxis fontSize={11} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#2563eb" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}
