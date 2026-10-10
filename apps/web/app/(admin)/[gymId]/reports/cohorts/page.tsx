"use client";

import { useQuery } from "@tanstack/react-query";
import { getCohortRetention } from "@fitkhata/api-client";

import { ReportsTabs } from "@/components/reports/reports-tabs";

function pct(retained: number, cohortSize: number): string {
  return cohortSize === 0 ? "—" : `${Math.round((retained / cohortSize) * 100)}%`;
}

function shade(retained: number, cohortSize: number): string {
  if (cohortSize === 0) return "";
  const p = retained / cohortSize;
  if (p >= 0.75) return "bg-green-600 text-white";
  if (p >= 0.5) return "bg-green-400 text-white";
  if (p >= 0.25) return "bg-green-200";
  return "bg-green-50";
}

export default function CohortRetentionPage() {
  const query = useQuery({
    queryKey: ["reports", "cohort-retention"],
    queryFn: getCohortRetention,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Reports</h1>
      <ReportsTabs />

      <h2 className="text-sm font-medium opacity-70">Cohort retention by join month</h2>
      {query.isLoading ? (
        <p className="text-sm opacity-60">Loading...</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left opacity-60">
                <th className="py-1">Join month</th>
                <th className="py-1 text-right">Cohort size</th>
                <th className="py-1 text-center">M1</th>
                <th className="py-1 text-center">M3</th>
                <th className="py-1 text-center">M6</th>
                <th className="py-1 text-center">M12</th>
              </tr>
            </thead>
            <tbody>
              {(query.data ?? []).map((row) => (
                <tr key={row.join_month} className="border-b">
                  <td className="py-1.5">{row.join_month}</td>
                  <td className="py-1.5 text-right">{row.cohort_size}</td>
                  {[row.retained_m1, row.retained_m3, row.retained_m6, row.retained_m12].map(
                    (retained, i) => (
                      <td key={i} className={`py-1.5 text-center ${shade(retained, row.cohort_size)}`}>
                        {pct(retained, row.cohort_size)}
                      </td>
                    )
                  )}
                </tr>
              ))}
              {(query.data ?? []).length === 0 && (
                <tr>
                  <td colSpan={6} className="py-3 text-center text-sm opacity-60">
                    No cohort data yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
