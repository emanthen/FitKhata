"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getPlanMix,
  getRevenueTrend,
  listPlans,
  type Plan,
} from "@fitkhata/api-client";
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

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ReportsTabs } from "@/components/reports/reports-tabs";
import { formatNpr } from "@/lib/money";

const COLORS = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed", "#0891b2"];

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
      <h1 className="text-2xl font-semibold">Reports</h1>
      <ReportsTabs />

      <div className="flex items-end gap-4">
        <div className="space-y-1">
          <Label htmlFor="from">From</Label>
          <Input id="from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="to">To</Label>
          <Input id="to" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded border p-4">
          <h2 className="mb-3 text-sm font-medium opacity-70">Revenue trend</h2>
          {trend.isLoading ? (
            <p className="text-sm opacity-60">Loading...</p>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" fontSize={11} />
                <YAxis fontSize={11} />
                <Tooltip formatter={(value) => formatNpr(Number(value ?? 0), { symbol: true })} />
                <Bar dataKey="amount" fill="#2563eb" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="rounded border p-4">
          <h2 className="mb-3 text-sm font-medium opacity-70">Plan mix</h2>
          {mix.isLoading ? (
            <p className="text-sm opacity-60">Loading...</p>
          ) : mixData.length === 0 ? (
            <p className="text-sm opacity-60">No revenue in this range.</p>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={mixData} dataKey="amount" nameKey="name" label={(e) => e.name}>
                  {mixData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => formatNpr(Number(value ?? 0), { symbol: true })} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}
