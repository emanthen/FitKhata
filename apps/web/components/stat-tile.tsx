import type { ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";

export function StatTile({
  label,
  value,
  icon,
  loading,
}: {
  label: string;
  value: string;
  icon: ReactNode;
  loading?: boolean;
}) {
  return (
    <div className="rounded-xl bg-card p-4 shadow-sm">
      <div className="flex items-center gap-2 text-muted-foreground">
        {icon}
        <p className="text-xs font-medium">{label}</p>
      </div>
      {loading ? (
        <Skeleton className="mt-2 h-7 w-20" />
      ) : (
        <p className="font-dashboard-mono mt-1.5 text-2xl font-semibold tabular-nums">{value}</p>
      )}
    </div>
  );
}
