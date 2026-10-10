"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createPayrollRun, listPayrollRuns, type PayrollRun } from "@fitkhata/api-client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StaffTabs } from "@/components/staff/staff-tabs";

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
      <h1 className="text-2xl font-semibold">Staff</h1>
      <StaffTabs />

      <form onSubmit={submit} className="flex flex-wrap items-end gap-3 rounded border p-3">
        <div className="space-y-1">
          <Label htmlFor="period-bs">Period (BS, YYYY-MM)</Label>
          <Input
            id="period-bs"
            placeholder="2083-06"
            value={periodBs}
            onChange={(e) => setPeriodBs(e.target.value)}
            className="w-32"
            required
          />
        </div>
        <Button type="submit" disabled={submitting}>
          {submitting ? "Computing..." : "Create / recompute run"}
        </Button>
      </form>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <p className="text-xs opacity-60">
        Creating a run for a period that already has a draft recomputes it in place — safe to
        re-run after fixing attendance or an advance, as long as it isn&apos;t finalized yet.
      </p>

      <ul className="space-y-2">
        {runs.map((run) => (
          <li key={run.id}>
            <Link
              href={`payroll/${run.id}`}
              className="flex items-center justify-between rounded border px-3 py-2 text-sm hover:bg-neutral-50 dark:hover:bg-neutral-900"
            >
              <span>{run.period_bs} BS</span>
              <span className="flex items-center gap-3">
                <span className="opacity-70">NPR {run.totals_npr}</span>
                <span
                  className={`rounded px-2 py-0.5 text-xs ${
                    run.status === "finalized"
                      ? "bg-green-100 text-green-800 dark:bg-green-950"
                      : "bg-amber-100 text-amber-800 dark:bg-amber-950"
                  }`}
                >
                  {run.status}
                </span>
              </span>
            </Link>
          </li>
        ))}
        {runs.length === 0 && <li className="text-sm opacity-60">No payroll runs yet.</li>}
      </ul>
    </div>
  );
}
