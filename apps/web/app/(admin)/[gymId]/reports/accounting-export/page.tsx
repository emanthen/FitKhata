"use client";

import { useState } from "react";
import { fetchAccountingExport, type AccountingExportFormat } from "@fitkhata/api-client";
import { ChartColumn, Download } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ReportsTabs } from "@/components/reports/reports-tabs";
import { useAuth } from "@/lib/auth";

async function downloadExport(date: string, format: AccountingExportFormat) {
  const blob = await fetchAccountingExport(date, format);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `accounting-export-${format}-${date}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function AccountingExportPage() {
  const { claims } = useAuth();
  const isOwner = claims?.role === "owner";
  const [date, setDate] = useState("");
  const [format, setFormat] = useState<AccountingExportFormat>("tally");
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    setError(null);
    setDownloading(true);
    try {
      await downloadExport(date, format);
    } catch {
      setError("Couldn't generate the export for that date.");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <ChartColumn size={18} strokeWidth={2} className="text-primary" />
        Reports
      </h1>
      <ReportsTabs />

      {!isOwner ? (
        <p className="text-sm text-muted-foreground">
          Only an owner can export the daily accounting journal.
        </p>
      ) : (
        <Card>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              One debit + credit row per payment collected on the chosen day, mapped to the
              column layout Tally or Swastik expects for voucher import — cash/bank/wallet
              clearing against Sales and VAT Payable.
            </p>
            <div className="flex flex-wrap items-end gap-2">
              <div className="space-y-1.5">
                <Label htmlFor="export-date">Date</Label>
                <Input
                  id="export-date"
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  className="h-8"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="export-format">Format</Label>
                <Select
                  value={format}
                  onValueChange={(v) => setFormat(v as AccountingExportFormat)}
                >
                  <SelectTrigger id="export-format" className="h-8 w-32 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="tally">Tally</SelectItem>
                    <SelectItem value="swastik">Swastik</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={download}
                disabled={!date || downloading}
              >
                <Download size={13} strokeWidth={2} data-icon="inline-start" />
                {downloading ? "..." : "Download CSV"}
              </Button>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
