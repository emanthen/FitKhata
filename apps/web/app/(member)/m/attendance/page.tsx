"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { getMemberAttendanceCalendar, type MemberAttendanceCalendar } from "@fitkhata/api-client";
import { Award, CalendarCheck, Flame } from "lucide-react";

import { getCachedPass } from "@/lib/member/pass";
import { adIsoToBsLabel } from "@/lib/bs-calendar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

type DateFormat = "ad" | "bs";

const STREAK_BADGE_THRESHOLDS = [7, 30, 100] as const;

export default function MemberAttendancePage() {
  const t = useTranslations("member");
  const router = useRouter();
  const [data, setData] = useState<MemberAttendanceCalendar | null>(null);
  const [format, setFormat] = useState<DateFormat>("ad");

  useEffect(() => {
    const pass = getCachedPass();
    if (!pass) {
      router.replace("/m");
      return;
    }
    getMemberAttendanceCalendar(pass.token)
      .then(setData)
      .catch(() => setData({ visit_dates: [], current_streak: 0, longest_streak: 0 }));
  }, [router]);

  if (!data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-7 w-40" />
        <Skeleton className="h-24 w-full rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <CalendarCheck size={18} strokeWidth={2} className="text-primary" />
        {t("attendanceTitle")}
      </h1>

      <div className="flex gap-2">
        <button
          onClick={() => setFormat("ad")}
          className={`h-9 flex-1 rounded-lg border text-sm font-medium transition-colors ${
            format === "ad" ? "border-primary bg-primary text-primary-foreground" : "text-muted-foreground"
          }`}
        >
          {t("attendanceToggleAd")}
        </button>
        <button
          onClick={() => setFormat("bs")}
          className={`h-9 flex-1 rounded-lg border text-sm font-medium transition-colors ${
            format === "bs" ? "border-primary bg-primary text-primary-foreground" : "text-muted-foreground"
          }`}
        >
          {t("attendanceToggleBs")}
        </button>
      </div>

      <Card>
        <CardContent className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Flame size={18} strokeWidth={2} className="text-accent" />
            <div>
              <p className="text-sm font-medium">{t("attendanceStreakCurrent", { count: data.current_streak })}</p>
              <p className="text-xs text-muted-foreground">
                {t("attendanceStreakLongest", { count: data.longest_streak })}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {STREAK_BADGE_THRESHOLDS.some((n) => data.current_streak >= n) && (
        <div className="flex flex-wrap gap-2">
          {STREAK_BADGE_THRESHOLDS.filter((n) => data.current_streak >= n).map((n) => (
            <Badge key={n} variant="secondary" className="gap-1">
              <Award size={11} strokeWidth={2} />
              {t(`attendanceBadge${n}` as "attendanceBadge7" | "attendanceBadge30" | "attendanceBadge100")}
            </Badge>
          ))}
        </div>
      )}

      {data.visit_dates.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("attendanceNoVisits")}</p>
      ) : (
        <ul className="grid grid-cols-4 gap-2 text-sm">
          {data.visit_dates
            .slice()
            .reverse()
            .map((d) => (
              <li
                key={d}
                className="font-dashboard-mono rounded-lg border bg-card px-2 py-2 text-center text-xs"
              >
                {format === "bs" ? adIsoToBsLabel(d) : d}
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}
