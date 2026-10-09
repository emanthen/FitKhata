"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  bookMemberClass,
  cancelMemberBooking,
  listMemberClasses,
  type ClassSchedule,
} from "@fitkhata/api-client";

import { getCachedPass } from "@/lib/member/pass";

type BookingState = { bookingId: string; status: "booked" | "waitlist" };

export default function MemberClassesPage() {
  const t = useTranslations("member");
  const router = useRouter();
  const [classes, setClasses] = useState<ClassSchedule[] | null>(null);
  const [bookings, setBookings] = useState<Record<string, BookingState>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const pass = getCachedPass();
    if (!pass) {
      router.replace("/m");
      return;
    }
    listMemberClasses(pass.token)
      .then(setClasses)
      .catch(() => setClasses([]));
  }, [router]);

  async function book(scheduleId: string) {
    const pass = getCachedPass();
    if (!pass) return;
    setError(null);
    try {
      const booking = await bookMemberClass(pass.token, scheduleId);
      setBookings((prev) => ({
        ...prev,
        [scheduleId]: { bookingId: booking.id, status: booking.status === "booked" ? "booked" : "waitlist" },
      }));
    } catch {
      setError(t("classesError"));
    }
  }

  async function cancel(scheduleId: string) {
    const pass = getCachedPass();
    const booking = bookings[scheduleId];
    if (!pass || !booking) return;
    setError(null);
    try {
      await cancelMemberBooking(pass.token, booking.bookingId);
      setBookings((prev) => {
        const next = { ...prev };
        delete next[scheduleId];
        return next;
      });
    } catch {
      setError(t("classesError"));
    }
  }

  if (!classes) return null;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">{t("classesTitle")}</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}

      {classes.length === 0 ? (
        <p className="text-sm opacity-60">{t("classesNone")}</p>
      ) : (
        <ul className="space-y-2">
          {classes.map((cls) => {
            const booking = bookings[cls.id];
            return (
              <li
                key={cls.id}
                className="flex items-center justify-between rounded border px-3 py-2 text-sm"
              >
                <span>
                  {cls.name}
                  <span className="ml-2 opacity-60">
                    {new Date(cls.starts_at).toLocaleString()}
                  </span>
                </span>
                {booking ? (
                  <button onClick={() => cancel(cls.id)} className="text-xs underline">
                    {booking.status === "waitlist" ? t("classesWaitlisted") : t("classesBooked")} ·{" "}
                    {t("classesCancel")}
                  </button>
                ) : (
                  <button
                    onClick={() => book(cls.id)}
                    className="rounded bg-black px-3 py-1 text-xs text-white"
                  >
                    {t("classesBook")}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
