"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { getDashboardSummary } from "@fitkhata/api-client";
import { Banknote, CalendarClock, DoorOpen, TrendingUp, Users } from "lucide-react";

import { RedListWidget } from "@/components/red-list-widget";
import { StatTile } from "@/components/stat-tile";
import { useGymFeed } from "@/lib/gym-feed";
import { formatNpr } from "@/lib/money";

export default function GymDashboardPage() {
  const { gymId } = useParams<{ gymId: string }>();
  const t = useTranslations("admin");
  const occupancy = useGymFeed(gymId);
  const { data, isLoading } = useQuery({
    queryKey: ["reports", "dashboard-summary", gymId],
    queryFn: getDashboardSummary,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold tracking-tight">{t("dashboardTitle")}</h1>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <StatTile
          label={t("dashboardActiveMembers")}
          icon={<Users size={16} strokeWidth={2} />}
          loading={isLoading}
          value={String(data?.active_members ?? 0)}
        />
        <StatTile
          label={t("dashboardRevenueToday")}
          icon={<Banknote size={16} strokeWidth={2} />}
          loading={isLoading}
          value={formatNpr(data?.revenue_today_npr ?? "0", { symbol: true })}
        />
        <StatTile
          label={t("dashboardRevenueMonth")}
          icon={<TrendingUp size={16} strokeWidth={2} />}
          loading={isLoading}
          value={formatNpr(data?.revenue_month_npr ?? "0", { symbol: true })}
        />
        <StatTile
          label={t("dashboardRenewalsDue")}
          icon={<CalendarClock size={16} strokeWidth={2} />}
          loading={isLoading}
          value={String(data?.renewals_due ?? 0)}
        />
        <StatTile
          label={t("dashboardInGymNow")}
          icon={<DoorOpen size={16} strokeWidth={2} />}
          loading={occupancy === null}
          value={String(occupancy ?? 0)}
        />
      </div>

      <RedListWidget />
    </div>
  );
}
