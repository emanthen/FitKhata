"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getPlanMix, getRevenueTrend, listPlans, type Plan } from "@fitkhata/api-client";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartColumn } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ReportsTabs } from "@/components/reports/reports-tabs";
import { formatNpr } from "@/lib/money";

const CHART_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function daysAgoIso(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

export default function ReportsOverviewPage() {
  const [from, setFrom] = useState(daysAgoIso(30));
  const [to, setTo] = useState(todayIso());

  const trend = useQuery({
    queryKey: ["reports", "revenue-trend", from, to],
    queryFn: () => getRevenueTrend({ from, to }),
  });
  const mix = useQuery({
    queryKey: ["reports", "plan-mix", from, to],
    queryFn: () => getPlanMix({ from, to }),
  });
  const plans = useQuery({ queryKey: ["plans"], queryFn: listPlans });

  const planName = (planId: string): string =>
    plans.data?.find((p: Plan) => p.id === planId)?.name ?? planId;

  const trendData = (trend.data ?? []).map((row) => ({
    day: row.day,
    amount: Number(row.amount_npr),
  }));
  const mixData = (mix.data ?? []).map((row) => ({
    name: planName(row.plan_id),
    amount: Number(row.amount_npr),
  }));

  return (
    <div className="space-y-6">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <ChartColumn size={18} strokeWidth={2} className="text-primary" />
        Reports
      </h1>
      <ReportsTabs />

      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="from">From</Label>
          <Input id="from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="h-8" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="to">To</Label>
          <Input id="to" type="date" value={to} onChange={(e) => setTo(e.target.value)} className="h-8" />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Revenue trend</CardTitle>
          </CardHeader>
          <CardContent>
            {trend.isLoading ? (
              <Skeleton className="h-[280px] w-full" />
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="day" fontSize={11} stroke="var(--muted-foreground)" />
                  <YAxis fontSize={11} stroke="var(--muted-foreground)" />
                  <Tooltip formatter={(value) => formatNpr(Number(value ?? 0), { symbol: true })} />
                  <Bar dataKey="amount" fill="var(--chart-1)" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">Plan mix</CardTitle>
          </CardHeader>
          <CardContent>
            {mix.isLoading ? (
              <Skeleton className="h-[280px] w-full" />
            ) : mixData.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted-foreground">
                No revenue in this range.
              </p>
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie data={mixData} dataKey="amount" nameKey="name" label={(e) => e.name}>
                    {mixData.map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => formatNpr(Number(value ?? 0), { symbol: true })} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
