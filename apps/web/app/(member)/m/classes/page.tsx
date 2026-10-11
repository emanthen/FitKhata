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
import { CalendarDays, TriangleAlert } from "lucide-react";

import { getCachedPass } from "@/lib/member/pass";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

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

  if (!classes) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-7 w-32" />
        <Skeleton className="h-16 w-full rounded-xl" />
        <Skeleton className="h-16 w-full rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <CalendarDays size={18} strokeWidth={2} className="text-primary" />
        {t("classesTitle")}
      </h1>
      {error && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <TriangleAlert size={14} strokeWidth={2} />
          {error}
        </p>
      )}

      {classes.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("classesNone")}</p>
      ) : (
        <ul className="space-y-2.5">
          {classes.map((cls) => {
            const booking = bookings[cls.id];
            return (
              <li key={cls.id}>
                <Card>
                  <CardContent className="flex items-center justify-between py-3">
                    <div>
                      <p className="text-sm font-medium">{cls.name}</p>
                      <p className="font-dashboard-mono text-xs text-muted-foreground">
                        {new Date(cls.starts_at).toLocaleString()}
                      </p>
                    </div>
                    {booking ? (
                      <div className="flex items-center gap-2">
                        <Badge variant={booking.status === "waitlist" ? "secondary" : "default"}>
                          {booking.status === "waitlist" ? t("classesWaitlisted") : t("classesBooked")}
                        </Badge>
                        <Button variant="ghost" size="sm" onClick={() => cancel(cls.id)}>
                          {t("classesCancel")}
                        </Button>
                      </div>
                    ) : (
                      <Button size="sm" onClick={() => book(cls.id)}>
                        {t("classesBook")}
                      </Button>
                    )}
                  </CardContent>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
