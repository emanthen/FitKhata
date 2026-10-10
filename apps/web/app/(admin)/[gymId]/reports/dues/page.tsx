"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchDuesAgeingExport, getDuesAgeing } from "@fitkhata/api-client";

import { Button } from "@/components/ui/button";
import { ReportsTabs } from "@/components/reports/reports-tabs";
import { formatNpr } from "@/lib/money";

const BUCKETS = ["0-30", "31-60", "60+"] as const;

async function downloadExport(format: "csv" | "xlsx") {
  const blob = await fetchDuesAgeingExport(format);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `dues-ageing.${format}`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function DuesAgeingPage() {
  const query = useQuery({ queryKey: ["reports", "dues-ageing"], queryFn: getDuesAgeing });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Reports</h1>
      <ReportsTabs />

      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium opacity-70">Dues ageing</h2>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => downloadExport("csv")}>
            Export CSV
          </Button>
          <Button variant="outline" onClick={() => downloadExport("xlsx")}>
            Export XLSX
          </Button>
        </div>
      </div>

      {query.isLoading ? (
        <p className="text-sm opacity-60">Loading...</p>
      ) : (
        <table className="w-full max-w-md text-sm">
          <thead>
            <tr className="border-b text-left opacity-60">
              <th className="py-1">Age bucket</th>
              <th className="py-1 text-right">Invoices</th>
              <th className="py-1 text-right">Total due</th>
            </tr>
          </thead>
          <tbody>
            {BUCKETS.map((bucket) => {
              const row = query.data?.[bucket];
              return (
                <tr key={bucket} className="border-b">
                  <td className="py-1.5">{bucket}</td>
                  <td className="py-1.5 text-right">{row?.count ?? 0}</td>
                  <td className="py-1.5 text-right">{formatNpr(row?.total_npr ?? "0")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
