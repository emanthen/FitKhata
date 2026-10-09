"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getRetentionDashboard } from "@fitkhata/api-client";

import { formatNpr } from "@/lib/money";

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border p-4">
      <p className="text-sm opacity-60">{label}</p>
      <p className="text-2xl font-semibold">{value}</p>
    </div>
  );
}

export default function RetentionDashboardPage() {
  const { gymId } = useParams<{ gymId: string }>();
  const query = useQuery({
    queryKey: ["retention", "dashboard"],
    queryFn: () => getRetentionDashboard(),
  });

  return (
    <div className="max-w-2xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Retention</h1>
        <div className="flex gap-3 text-sm">
          <Link href={`/${gymId}/retention/queue`} className="text-blue-600 hover:underline">
            Call queue
          </Link>
          <Link href={`/${gymId}/retention/freeze`} className="text-blue-600 hover:underline">
            Freeze wizard
          </Link>
        </div>
      </div>

      {query.isLoading && <p className="text-sm opacity-60">Loading...</p>}

      {query.data && (
        <div className="grid grid-cols-3 gap-3">
          <StatCard label="Churn rate this month" value={`${(query.data.churn_rate * 100).toFixed(1)}%`} />
          <StatCard label="Saves this month" value={String(query.data.saves_this_month)} />
          <StatCard
            label="Revenue protected"
            value={formatNpr(query.data.revenue_protected_npr, { symbol: true })}
          />
        </div>
      )}
    </div>
  );
}
