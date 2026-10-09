"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSettlementReport } from "@fitkhata/api-client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatNpr } from "@/lib/money";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

const MODE_LABELS: Record<string, string> = {
  cash: "Cash",
  manual_esewa: "Manual eSewa",
  bank: "Bank transfer",
  cheque: "Cheque",
  esewa: "eSewa",
  khalti: "Khalti",
  fonepay: "Fonepay",
};

export default function SettlementReportPage() {
  const [date, setDate] = useState(today());
  const report = useQuery({
    queryKey: ["settlement-report", date],
    queryFn: () => getSettlementReport(date),
  });

  return (
    <div className="max-w-md space-y-4">
      <h1 className="text-2xl font-semibold">Daily settlement</h1>

      <div className="space-y-1">
        <Label htmlFor="report-date">Date</Label>
        <Input
          id="report-date"
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="w-44"
        />
      </div>

      {report.isLoading && <p className="text-sm opacity-60">Loading...</p>}

      {report.data && (
        <div className="space-y-2">
          <ul className="space-y-1 text-sm">
            {Object.entries(report.data.by_mode).map(([mode, amount]) => (
              <li key={mode} className="flex justify-between rounded border px-3 py-2">
                <span>{MODE_LABELS[mode] ?? mode}</span>
                <span>{formatNpr(amount, { symbol: true })}</span>
              </li>
            ))}
            {Object.keys(report.data.by_mode).length === 0 && (
              <li className="text-sm opacity-60">No payments collected on this date.</li>
            )}
          </ul>
          <div className="flex justify-between border-t pt-2 text-base font-semibold">
            <span>Total</span>
            <span>{formatNpr(report.data.total_npr, { symbol: true })}</span>
          </div>
        </div>
      )}
    </div>
  );
}
