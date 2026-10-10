"use client";

import { useQuery } from "@tanstack/react-query";
import { getAttendanceHeatmap } from "@fitkhata/api-client";

import { ReportsTabs } from "@/components/reports/reports-tabs";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

function intensity(count: number, max: number): string {
  if (max === 0 || count === 0) return "bg-neutral-50 dark:bg-neutral-900";
  const pct = count / max;
  if (pct > 0.75) return "bg-blue-700 text-white";
  if (pct > 0.5) return "bg-blue-500 text-white";
  if (pct > 0.25) return "bg-blue-300";
  return "bg-blue-100";
}

export default function AttendanceHeatmapPage() {
  const query = useQuery({
    queryKey: ["reports", "attendance-heatmap"],
    queryFn: getAttendanceHeatmap,
  });

  const byCell = new Map<string, number>();
  let max = 0;
  for (const row of query.data ?? []) {
    byCell.set(`${row.weekday}-${row.hour}`, row.count);
    max = Math.max(max, row.count);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Reports</h1>
      <ReportsTabs />

      <h2 className="text-sm font-medium opacity-70">Attendance by hour of day</h2>
      {query.isLoading ? (
        <p className="text-sm opacity-60">Loading...</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="border-collapse text-xs">
            <thead>
              <tr>
                <th className="w-10" />
                {HOURS.map((h) => (
                  <th key={h} className="px-1 py-0.5 text-center font-normal opacity-60">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {WEEKDAYS.map((label, weekday) => (
                <tr key={weekday}>
                  <td className="pr-2 text-right opacity-60">{label}</td>
                  {HOURS.map((hour) => {
                    const count = byCell.get(`${weekday}-${hour}`) ?? 0;
                    return (
                      <td
                        key={hour}
                        title={`${label} ${hour}:00 — ${count}`}
                        className={`h-6 w-6 border text-center ${intensity(count, max)}`}
                      >
                        {count > 0 ? count : ""}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
