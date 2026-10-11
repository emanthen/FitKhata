"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createPayrollRun, listPayrollRuns, type PayrollRun } from "@fitkhata/api-client";
import { IdCard, TriangleAlert, Wallet } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StaffTabs } from "@/components/staff/staff-tabs";
import { formatNpr } from "@/lib/money";

function toList(data: PayrollRun[] | { results: PayrollRun[] } | undefined): PayrollRun[] {
  if (!data) return [];
  return Array.isArray(data) ? data : data.results;
}

export default function PayrollPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [periodBs, setPeriodBs] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const query = useQuery({ queryKey: ["staff", "payroll-runs"], queryFn: listPayrollRuns });
  const runs = toList(query.data);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const run = await createPayrollRun(periodBs);
      queryClient.invalidateQueries({ queryKey: ["staff", "payroll-runs"] });
      router.push(`payroll/${run.id}`);
    } catch {
      setError("Couldn't create that payroll run — check the period format (BS YYYY-MM).");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <IdCard size={18} strokeWidth={2} className="text-primary" />
        Staff
      </h1>
      <StaffTabs />

      <Card>
        <CardContent className="space-y-3">
          <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="period-bs">Period (BS, YYYY-MM)</Label>
              <Input
                id="period-bs"
                placeholder="2083-06"
                value={periodBs}
                onChange={(e) => setPeriodBs(e.target.value)}
                className="h-8 w-32"
                required
              />
            </div>
            <Button type="submit" size="sm" disabled={submitting}>
              {submitting ? "Computing..." : "Create / recompute run"}
            </Button>
          </form>
          <p className="text-xs text-muted-foreground">
            Creating a run for a period that already has a draft recomputes it in place - safe to
            re-run after fixing attendance or an advance, as long as it isn&apos;t finalized yet.
          </p>
        </CardContent>
      </Card>
      {error && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <TriangleAlert size={14} strokeWidth={2} />
          {error}
        </p>
      )}

      <Card>
        <CardContent>
          <ul className="divide-y">
            {runs.map((run) => (
              <li key={run.id}>
                <Link
                  href={`payroll/${run.id}`}
                  className="-mx-(--card-spacing) flex items-center justify-between px-(--card-spacing) py-2.5 text-sm transition-colors hover:bg-muted"
                >
                  <span className="flex items-center gap-2">
                    <Wallet size={14} strokeWidth={2} className="text-muted-foreground" />
                    {run.period_bs} BS
                  </span>
                  <span className="flex items-center gap-3">
                    <span className="font-dashboard-mono text-muted-foreground">
                      {formatNpr(run.totals_npr, { symbol: true })}
                    </span>
                    <Badge variant={run.status === "finalized" ? "default" : "secondary"}>
                      {run.status}
                    </Badge>
                  </span>
                </Link>
              </li>
            ))}
            {runs.length === 0 && (
              <li className="py-2.5 text-sm text-muted-foreground">No payroll runs yet.</li>
            )}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
