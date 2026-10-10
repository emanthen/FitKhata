"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getDashboardSummary } from "@fitkhata/api-client";

import { RedListWidget } from "@/components/red-list-widget";
import { useGymFeed } from "@/lib/gym-feed";
import { formatNpr } from "@/lib/money";

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border p-4">
      <p className="text-sm opacity-70">{label}</p>
      <p className="text-2xl font-semibold">{value}</p>
    </div>
  );
}

export default function GymDashboardPage() {
  const { gymId } = useParams<{ gymId: string }>();
  const occupancy = useGymFeed(gymId);
  const { data, isLoading } = useQuery({
    queryKey: ["reports", "dashboard-summary", gymId],
    queryFn: getDashboardSummary,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <StatTile label="Active members" value={isLoading ? "..." : String(data?.active_members ?? 0)} />
        <StatTile
          label="Revenue today"
          value={isLoading ? "..." : formatNpr(data?.revenue_today_npr ?? "0")}
        />
        <StatTile
          label="Revenue this month"
          value={isLoading ? "..." : formatNpr(data?.revenue_month_npr ?? "0")}
        />
        <StatTile label="Renewals due (7d)" value={isLoading ? "..." : String(data?.renewals_due ?? 0)} />
        <StatTile label="In gym now" value={occupancy === null ? "..." : String(occupancy)} />
      </div>
      <RedListWidget />
    </div>
  );
}
