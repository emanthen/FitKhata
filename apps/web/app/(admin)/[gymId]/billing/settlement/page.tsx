"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSettlementReport } from "@fitkhata/api-client";
import { Receipt } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
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
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <Receipt size={18} strokeWidth={2} className="text-primary" />
        Daily settlement
      </h1>

      <div className="space-y-1.5">
        <Label htmlFor="report-date">Date</Label>
        <Input
          id="report-date"
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="w-44"
        />
      </div>

      <Card>
        <CardContent>
          {report.isLoading && (
            <div className="space-y-2">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
            </div>
          )}

          {report.data && (
            <div className="space-y-2">
              <ul className="divide-y">
                {Object.entries(report.data.by_mode).map(([mode, amount]) => (
                  <li key={mode} className="flex items-center justify-between py-2 text-sm">
                    <span>{MODE_LABELS[mode] ?? mode}</span>
                    <span className="font-dashboard-mono">{formatNpr(amount, { symbol: true })}</span>
                  </li>
                ))}
                {Object.keys(report.data.by_mode).length === 0 && (
                  <li className="py-2 text-sm text-muted-foreground">
                    No payments collected on this date.
                  </li>
                )}
              </ul>
              <div className="flex items-center justify-between border-t pt-3 text-base font-semibold">
                <span>Total</span>
                <span className="font-dashboard-mono">
                  {formatNpr(report.data.total_npr, { symbol: true })}
                </span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
