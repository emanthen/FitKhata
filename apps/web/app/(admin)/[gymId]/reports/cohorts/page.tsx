"use client";

import { useQuery } from "@tanstack/react-query";
import { getCohortRetention } from "@fitkhata/api-client";
import { ChartColumn } from "lucide-react";
import { useTranslations } from "next-intl";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ReportsTabs } from "@/components/reports/reports-tabs";

function pct(retained: number, cohortSize: number): string {
  return cohortSize === 0 ? "-" : `${Math.round((retained / cohortSize) * 100)}%`;
}

function shade(retained: number, cohortSize: number): string {
  if (cohortSize === 0) return "";
  const p = retained / cohortSize;
  if (p >= 0.75) return "bg-accent text-accent-foreground";
  if (p >= 0.5) return "bg-accent/70 text-white";
  if (p >= 0.25) return "bg-accent/35";
  return "bg-accent/15";
}

export default function CohortRetentionPage() {
  const t = useTranslations("admin");
  const query = useQuery({
    queryKey: ["reports", "cohort-retention"],
    queryFn: getCohortRetention,
  });

  return (
    <div className="space-y-6">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <ChartColumn size={18} strokeWidth={2} className="text-primary" />
        {t("reportsHeading")}
      </h1>
      <ReportsTabs />

      <Card>
        <CardContent>
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">
            {t("reportsCohortTitle")}
          </h2>
          {query.isLoading ? (
            <Skeleton className="h-48 w-full" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-1.5">{t("reportsCohortJoinMonth")}</th>
                    <th className="py-1.5 text-right">{t("reportsCohortSize")}</th>
                    <th className="py-1.5 text-center">M1</th>
                    <th className="py-1.5 text-center">M3</th>
                    <th className="py-1.5 text-center">M6</th>
                    <th className="py-1.5 text-center">M12</th>
                  </tr>
                </thead>
                <tbody className="font-dashboard-mono">
                  {(query.data ?? []).map((row) => (
                    <tr key={row.join_month} className="border-b">
                      <td className="py-1.5 font-sans">{row.join_month}</td>
                      <td className="py-1.5 text-right">{row.cohort_size}</td>
                      {[row.retained_m1, row.retained_m3, row.retained_m6, row.retained_m12].map(
                        (retained, i) => (
                          <td
                            key={i}
                            className={`py-1.5 text-center ${shade(retained, row.cohort_size)}`}
                          >
                            {pct(retained, row.cohort_size)}
                          </td>
                        )
                      )}
                    </tr>
                  ))}
                  {(query.data ?? []).length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-6 text-center font-sans text-sm text-muted-foreground">
                        {t("reportsCohortNoData")}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
