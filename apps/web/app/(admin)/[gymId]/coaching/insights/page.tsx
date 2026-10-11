"use client";

import { useQuery } from "@tanstack/react-query";
import { getOwnerCoachingInsights } from "@fitkhata/api-client";
import { Brain, TriangleAlert } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatNpr } from "@/lib/money";

export default function CoachingInsightsPage() {
  const query = useQuery({ queryKey: ["coaching", "owner-insights"], queryFn: getOwnerCoachingInsights });

  if (query.isLoading) {
    return (
      <div className="max-w-2xl space-y-6">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-32 w-full rounded-xl" />
      </div>
    );
  }
  const data = query.data;
  if (!data) return null;

  const report = data.latest_branch_report;
  const flags = report?.flags as
    | { flag_counts?: { flag: string; count: number }[]; approval_rate_pct?: number }
    | undefined;
  const spendPct = (Number(data.ai_spend_npr_month_to_date) / data.ai_budget_npr_monthly) * 100;

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <Brain size={18} strokeWidth={2} className="text-primary" />
        AI coaching insights
      </h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-muted-foreground">AI budget this month</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="font-dashboard-mono text-sm">
            {formatNpr(data.ai_spend_npr_month_to_date, { symbol: true })} of{" "}
            {formatNpr(String(data.ai_budget_npr_monthly), { symbol: true })} spent
          </p>
          <div className="h-2 w-full rounded-full bg-muted">
            <div
              className={`h-2 rounded-full ${spendPct >= 100 ? "bg-destructive" : "bg-primary"}`}
              style={{ width: `${Math.min(100, spendPct)}%` }}
            />
          </div>
          {spendPct >= 100 && (
            <p className="flex items-center gap-1.5 text-xs text-destructive">
              <TriangleAlert size={12} strokeWidth={2} />
              Budget exceeded - new AI reports fall back to rules-only suggestions until next
              month.
            </p>
          )}
        </CardContent>
      </Card>

      {report ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">
              Latest branch report &middot; week of {report.week_start}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm">
              Trainer approval rate:{" "}
              <span className="font-dashboard-mono font-medium">{flags?.approval_rate_pct ?? 0}%</span>
            </p>
            <div className="space-y-1.5">
              <p className="text-sm font-medium">Top risks this week</p>
              <ul className="divide-y text-sm">
                {flags?.flag_counts?.map((f) => (
                  <li key={f.flag} className="flex items-center justify-between py-1.5">
                    <span className="capitalize">{f.flag.replace(/_/g, " ")}</span>
                    <span className="font-dashboard-mono text-muted-foreground">
                      {f.count} client(s)
                    </span>
                  </li>
                ))}
                {(!flags?.flag_counts || flags.flag_counts.length === 0) && (
                  <li className="py-1.5 text-muted-foreground">No flags this week.</li>
                )}
              </ul>
            </div>
          </CardContent>
        </Card>
      ) : (
        <p className="text-sm text-muted-foreground">No branch report has been generated yet.</p>
      )}
    </div>
  );
}
