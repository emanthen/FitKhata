"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchPayslipPdf,
  finalizePayrollRun,
  getPayrollRun,
  listStaffProfiles,
  setPayslipIncentives,
  type StaffProfile,
} from "@fitkhata/api-client";
import { Lock, TriangleAlert, Wallet } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";

function toList(
  data: StaffProfile[] | { results: StaffProfile[] } | undefined
): StaffProfile[] {
  if (!data) return [];
  return Array.isArray(data) ? data : data.results;
}

async function downloadPdf(payslipId: string, lang: "en" | "ne") {
  const blob = await fetchPayslipPdf(payslipId, lang);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `payslip-${payslipId}-${lang}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function PayrollRunPage() {
  const { runId } = useParams<{ runId: string }>();
  const { claims } = useAuth();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [editingIncentives, setEditingIncentives] = useState<Record<string, string>>({});

  const runQuery = useQuery({
    queryKey: ["staff", "payroll-run", runId],
    queryFn: () => getPayrollRun(runId),
  });
  const staffQuery = useQuery({ queryKey: ["staff", "profiles"], queryFn: listStaffProfiles });
  const staffById = new Map(toList(staffQuery.data).map((s) => [s.id, s]));

  const run = runQuery.data;
  const locked = run?.status === "finalized";

  async function saveIncentives(payslipId: string) {
    const value = editingIncentives[payslipId];
    if (value === undefined) return;
    try {
      await setPayslipIncentives(payslipId, value);
      queryClient.invalidateQueries({ queryKey: ["staff", "payroll-run", runId] });
    } catch {
      setError("Couldn't save incentives — the run may already be finalized.");
    }
  }

  async function finalize() {
    setError(null);
    try {
      await finalizePayrollRun(runId);
      queryClient.invalidateQueries({ queryKey: ["staff", "payroll-run", runId] });
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data
        ?.detail;
      setError(detail ?? "Couldn't finalize this run.");
    }
  }

  if (!run) {
    return (
      <div className="max-w-4xl space-y-6">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-60 w-full rounded-xl" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <Wallet size={18} strokeWidth={2} className="text-primary" />
          Payroll &mdash; {run.period_bs} BS
        </h1>
        <Badge variant={locked ? "default" : "secondary"}>{run.status}</Badge>
      </div>

      {error && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <TriangleAlert size={14} strokeWidth={2} />
          {error}
        </p>
      )}

      {claims?.role === "owner" && !locked && (
        <Button onClick={finalize} size="sm">
          <Lock size={13} strokeWidth={2} data-icon="inline-start" />
          Finalize - locks this run permanently
        </Button>
      )}
      {claims?.role !== "owner" && !locked && (
        <p className="text-xs text-muted-foreground">Only an owner can finalize this run.</p>
      )}

      <Card>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-1.5">Staff</th>
                  <th className="py-1.5 text-right">Base</th>
                  <th className="py-1.5 text-right">Commission</th>
                  <th className="py-1.5 text-right">Incentives</th>
                  <th className="py-1.5 text-right">Advances</th>
                  <th className="py-1.5 text-right">TDS</th>
                  <th className="py-1.5 text-right">Net</th>
                  <th className="py-1.5">Payslip</th>
                </tr>
              </thead>
              <tbody className="font-dashboard-mono">
                {run.payslips.map((p) => (
                  <tr key={p.id} className="border-b">
                    <td className="py-1.5 font-sans">
                      {staffById.get(p.staff)?.full_name ?? staffById.get(p.staff)?.badge_code ?? p.staff}
                    </td>
                    <td className="py-1.5 text-right">{p.base_npr}</td>
                    <td className="py-1.5 text-right">{p.commission_npr}</td>
                    <td className="py-1.5 text-right">
                      {locked ? (
                        p.incentives_npr
                      ) : (
                        <div className="flex items-center justify-end gap-1">
                          <Input
                            className="h-7 w-20 text-right"
                            defaultValue={p.incentives_npr}
                            onChange={(e) =>
                              setEditingIncentives((prev) => ({ ...prev, [p.id]: e.target.value }))
                            }
                          />
                          <Button size="sm" className="h-7 px-2 font-sans" onClick={() => saveIncentives(p.id)}>
                            Save
                          </Button>
                        </div>
                      )}
                    </td>
                    <td className="py-1.5 text-right">{p.advances_npr}</td>
                    <td className="py-1.5 text-right">{p.tds_npr}</td>
                    <td className="py-1.5 text-right font-medium">{p.net_npr}</td>
                    <td className="py-1.5 font-sans">
                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 px-1.5 text-xs text-primary hover:text-primary"
                          onClick={() => downloadPdf(p.id, "en")}
                        >
                          EN
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 px-1.5 text-xs text-primary hover:text-primary"
                          onClick={() => downloadPdf(p.id, "ne")}
                        >
                          NE
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
