"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { getStaffLeaderboard } from "@fitkhata/api-client";
import { IdCard, Trophy } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StaffTabs } from "@/components/staff/staff-tabs";

export default function LeaderboardPage() {
  const t = useTranslations("admin");
  const [periodBs, setPeriodBs] = useState("");

  const query = useQuery({
    queryKey: ["staff", "leaderboard", periodBs],
    queryFn: () => getStaffLeaderboard(periodBs),
    enabled: periodBs.length > 0,
  });

  const rows = [...(query.data ?? [])].sort((a, b) => b.renewals_sold - a.renewals_sold);

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <IdCard size={18} strokeWidth={2} className="text-primary" />
        {t("staffPageTitle")}
      </h1>
      <StaffTabs />

      <div className="space-y-1.5">
        <Label htmlFor="leaderboard-period">{t("staffLeaderboardPeriodLabel")}</Label>
        <Input
          id="leaderboard-period"
          placeholder="2083-06"
          value={periodBs}
          onChange={(e) => setPeriodBs(e.target.value)}
          className="h-8 w-32"
        />
      </div>

      {periodBs && (
        <Card>
          <CardContent>
            <h2 className="mb-3 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
              <Trophy size={14} strokeWidth={2} />
              {t("staffLeaderboardRankings")}
            </h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-1.5">{t("staffLeaderboardColumnStaff")}</th>
                  <th className="py-1.5 text-right">{t("staffLeaderboardColumnRenewalsSold")}</th>
                  <th className="py-1.5 text-right">{t("staffLeaderboardColumnRenewalsNpr")}</th>
                  <th className="py-1.5 text-right">{t("staffLeaderboardColumnCallsCompleted")}</th>
                  <th className="py-1.5 text-right">{t("staffLeaderboardColumnSaves")}</th>
                </tr>
              </thead>
              <tbody className="font-dashboard-mono">
                {rows.map((row) => (
                  <tr key={row.staff_id} className="border-b">
                    <td className="py-1.5 font-sans">{row.full_name || row.badge_code}</td>
                    <td className="py-1.5 text-right">{row.renewals_sold}</td>
                    <td className="py-1.5 text-right">{row.renewals_npr}</td>
                    <td className="py-1.5 text-right">{row.calls_completed}</td>
                    <td className="py-1.5 text-right">{row.saves}</td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-6 text-center font-sans text-sm text-muted-foreground">
                      {t("staffLeaderboardEmpty")}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
