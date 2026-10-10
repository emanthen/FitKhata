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

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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

  if (!run) return null;

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Payroll — {run.period_bs} BS</h1>
        <span
          className={`rounded px-2 py-0.5 text-xs ${
            locked
              ? "bg-green-100 text-green-800 dark:bg-green-950"
              : "bg-amber-100 text-amber-800 dark:bg-amber-950"
          }`}
        >
          {run.status}
        </span>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {claims?.role === "owner" && !locked && (
        <Button onClick={finalize}>Finalize — locks this run permanently</Button>
      )}
      {claims?.role !== "owner" && !locked && (
        <p className="text-xs opacity-60">Only an owner can finalize this run.</p>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left opacity-60">
              <th className="py-1">Staff</th>
              <th className="py-1 text-right">Base</th>
              <th className="py-1 text-right">Commission</th>
              <th className="py-1 text-right">Incentives</th>
              <th className="py-1 text-right">Advances</th>
              <th className="py-1 text-right">TDS</th>
              <th className="py-1 text-right">Net</th>
              <th className="py-1">Payslip</th>
            </tr>
          </thead>
          <tbody>
            {run.payslips.map((p) => (
              <tr key={p.id} className="border-b">
                <td className="py-1.5">
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
                      <Button size="sm" className="h-7 px-2" onClick={() => saveIncentives(p.id)}>
                        Save
                      </Button>
                    </div>
                  )}
                </td>
                <td className="py-1.5 text-right">{p.advances_npr}</td>
                <td className="py-1.5 text-right">{p.tds_npr}</td>
                <td className="py-1.5 text-right font-medium">{p.net_npr}</td>
                <td className="py-1.5">
                  <div className="flex gap-2">
                    <button
                      className="text-xs underline"
                      onClick={() => downloadPdf(p.id, "en")}
                    >
                      EN
                    </button>
                    <button
                      className="text-xs underline"
                      onClick={() => downloadPdf(p.id, "ne")}
                    >
                      NE
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
