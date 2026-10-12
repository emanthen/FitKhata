"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchDuesAgeingExport, getDuesAgeing } from "@fitkhata/api-client";
import { ChartColumn, Download } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
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
  const t = useTranslations("admin");
  const query = useQuery({ queryKey: ["reports", "dues-ageing"], queryFn: getDuesAgeing });

  return (
    <div className="space-y-6">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <ChartColumn size={18} strokeWidth={2} className="text-primary" />
        {t("reportsHeading")}
      </h1>
      <ReportsTabs />

      <Card>
        <CardContent>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium text-muted-foreground">{t("reportsDuesTitle")}</h2>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => downloadExport("csv")}>
                <Download size={13} strokeWidth={2} data-icon="inline-start" />
                {t("reportsCsv")}
              </Button>
              <Button variant="outline" size="sm" onClick={() => downloadExport("xlsx")}>
                <Download size={13} strokeWidth={2} data-icon="inline-start" />
                {t("reportsXlsx")}
              </Button>
            </div>
          </div>

          {query.isLoading ? (
            <Skeleton className="h-28 w-full max-w-md" />
          ) : (
            <table className="w-full max-w-md text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-1.5">{t("reportsDuesAgeBucket")}</th>
                  <th className="py-1.5 text-right">{t("reportsDuesInvoices")}</th>
                  <th className="py-1.5 text-right">{t("reportsDuesTotalDue")}</th>
                </tr>
              </thead>
              <tbody className="font-dashboard-mono">
                {BUCKETS.map((bucket) => {
                  const row = query.data?.[bucket];
                  return (
                    <tr key={bucket} className="border-b">
                      <td className="py-1.5 font-sans">{bucket}</td>
                      <td className="py-1.5 text-right">{row?.count ?? 0}</td>
                      <td className="py-1.5 text-right">{formatNpr(row?.total_npr ?? "0")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
