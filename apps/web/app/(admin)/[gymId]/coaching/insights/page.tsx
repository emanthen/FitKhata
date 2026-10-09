"use client";

import { useQuery } from "@tanstack/react-query";
import { getOwnerCoachingInsights } from "@fitkhata/api-client";

import { formatNpr } from "@/lib/money";

export default function CoachingInsightsPage() {
  const query = useQuery({ queryKey: ["coaching", "owner-insights"], queryFn: getOwnerCoachingInsights });

  if (query.isLoading) return <p className="text-sm opacity-60">Loading...</p>;
  const data = query.data;
  if (!data) return null;

  const report = data.latest_branch_report;
  const flags = report?.flags as
    | { flag_counts?: { flag: string; count: number }[]; approval_rate_pct?: number }
    | undefined;
  const spendPct = (Number(data.ai_spend_npr_month_to_date) / data.ai_budget_npr_monthly) * 100;

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">AI coaching insights</h1>

      <section className="space-y-2 rounded border p-4">
        <h2 className="text-lg font-medium">AI budget this month</h2>
        <p className="text-sm">
          {formatNpr(data.ai_spend_npr_month_to_date, { symbol: true })} of{" "}
          {formatNpr(String(data.ai_budget_npr_monthly), { symbol: true })} spent
        </p>
        <div className="h-2 w-full rounded bg-muted">
          <div
            className={`h-2 rounded ${spendPct >= 100 ? "bg-red-600" : "bg-primary"}`}
            style={{ width: `${Math.min(100, spendPct)}%` }}
          />
        </div>
        {spendPct >= 100 && (
          <p className="text-xs text-red-600">
            Budget exceeded — new AI reports fall back to rules-only suggestions until next month.
          </p>
        )}
      </section>

      {report ? (
        <section className="space-y-3 rounded border p-4">
          <h2 className="text-lg font-medium">Latest branch report &middot; week of {report.week_start}</h2>
          <p className="text-sm">
            Trainer approval rate:{" "}
            <span className="font-medium">{flags?.approval_rate_pct ?? 0}%</span>
          </p>
          <div className="space-y-1">
            <p className="text-sm font-medium">Top risks this week</p>
            <ul className="space-y-1 text-sm">
              {flags?.flag_counts?.map((f) => (
                <li key={f.flag} className="flex justify-between rounded border px-3 py-1">
                  <span className="capitalize">{f.flag.replace(/_/g, " ")}</span>
                  <span className="opacity-60">{f.count} client(s)</span>
                </li>
              ))}
              {(!flags?.flag_counts || flags.flag_counts.length === 0) && (
                <li className="text-sm opacity-60">No flags this week.</li>
              )}
            </ul>
          </div>
        </section>
      ) : (
        <p className="text-sm opacity-60">No branch report has been generated yet.</p>
      )}
    </div>
  );
}
