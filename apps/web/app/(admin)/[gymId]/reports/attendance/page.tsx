"use client";

import { useQuery } from "@tanstack/react-query";
import { getAttendanceHeatmap } from "@fitkhata/api-client";
import { ChartColumn } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ReportsTabs } from "@/components/reports/reports-tabs";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

function intensity(count: number, max: number): string {
  if (max === 0 || count === 0) return "bg-muted/60";
  const pct = count / max;
  if (pct > 0.75) return "bg-primary text-primary-foreground";
  if (pct > 0.5) return "bg-primary/70 text-white";
  if (pct > 0.25) return "bg-primary/35";
  return "bg-primary/15";
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
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <ChartColumn size={18} strokeWidth={2} className="text-primary" />
        Reports
      </h1>
      <ReportsTabs />

      <Card>
        <CardContent>
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">
            Attendance by hour of day
          </h2>
          {query.isLoading ? (
            <Skeleton className="h-48 w-full" />
          ) : (
            <div className="font-dashboard-mono overflow-x-auto">
              <table className="border-collapse text-xs">
                <thead>
                  <tr>
                    <th className="w-10" />
                    {HOURS.map((h) => (
                      <th key={h} className="px-1 py-0.5 text-center font-normal text-muted-foreground">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {WEEKDAYS.map((label, weekday) => (
                    <tr key={weekday}>
                      <td className="pr-2 text-right text-muted-foreground">{label}</td>
                      {HOURS.map((hour) => {
                        const count = byCell.get(`${weekday}-${hour}`) ?? 0;
                        return (
                          <td
                            key={hour}
                            title={`${label} ${hour}:00 - ${count}`}
                            className={`h-6 w-6 rounded-[2px] text-center ${intensity(count, max)}`}
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
        </CardContent>
      </Card>
    </div>
  );
}
