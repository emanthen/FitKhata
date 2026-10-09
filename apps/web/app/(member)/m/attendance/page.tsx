"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { getMemberAttendanceCalendar, type MemberAttendanceCalendar } from "@fitkhata/api-client";

import { getCachedPass } from "@/lib/member/pass";
import { adIsoToBsLabel } from "@/lib/bs-calendar";

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

  if (!data) return null;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">{t("attendanceTitle")}</h1>

      <div className="flex gap-2 text-sm">
        <button
          onClick={() => setFormat("ad")}
          className={`rounded border px-3 py-1 ${format === "ad" ? "bg-black text-white" : ""}`}
        >
          {t("attendanceToggleAd")}
        </button>
        <button
          onClick={() => setFormat("bs")}
          className={`rounded border px-3 py-1 ${format === "bs" ? "bg-black text-white" : ""}`}
        >
          {t("attendanceToggleBs")}
        </button>
      </div>

      <div className="space-y-1 text-sm">
        <p>{t("attendanceStreakCurrent", { count: data.current_streak })}</p>
        <p className="opacity-70">{t("attendanceStreakLongest", { count: data.longest_streak })}</p>
      </div>

      <div className="flex gap-2">
        {STREAK_BADGE_THRESHOLDS.filter((n) => data.current_streak >= n).map((n) => (
          <span
            key={n}
            className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800"
          >
            {t(`attendanceBadge${n}` as "attendanceBadge7" | "attendanceBadge30" | "attendanceBadge100")}
          </span>
        ))}
      </div>

      {data.visit_dates.length === 0 ? (
        <p className="text-sm opacity-60">{t("attendanceNoVisits")}</p>
      ) : (
        <ul className="grid grid-cols-4 gap-2 text-sm">
          {data.visit_dates
            .slice()
            .reverse()
            .map((d) => (
              <li key={d} className="rounded border px-2 py-1 text-center">
                {format === "bs" ? adIsoToBsLabel(d) : d}
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}
