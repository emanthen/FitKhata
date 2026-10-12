"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  bookClass,
  cancelBooking,
  createClassSchedule,
  listClassBookings,
  listClassSchedules,
} from "@fitkhata/api-client";
import { CalendarDays, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function ClassesPage() {
  const t = useTranslations("admin");
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [capacity, setCapacity] = useState("10");
  const [memberIdToBook, setMemberIdToBook] = useState("");
  const [selectedClass, setSelectedClass] = useState<string | null>(null);

  const classes = useQuery({ queryKey: ["coaching", "classes"], queryFn: listClassSchedules });
  const classList = Array.isArray(classes.data) ? classes.data : classes.data?.results ?? [];

  const bookings = useQuery({
    queryKey: ["coaching", "bookings", selectedClass],
    queryFn: () => listClassBookings(selectedClass ?? undefined),
    enabled: Boolean(selectedClass),
  });
  const bookingList = Array.isArray(bookings.data) ? bookings.data : bookings.data?.results ?? [];

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["coaching", "classes"] });
    queryClient.invalidateQueries({ queryKey: ["coaching", "bookings"] });
  }

  async function createClass(e: React.FormEvent) {
    e.preventDefault();
    await createClassSchedule({ name, starts_at: startsAt, capacity: Number(capacity) });
    setName("");
    setStartsAt("");
    refresh();
  }

  async function book() {
    if (!selectedClass || !memberIdToBook) return;
    await bookClass({ class_schedule: selectedClass, member: memberIdToBook });
    setMemberIdToBook("");
    refresh();
  }

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <CalendarDays size={18} strokeWidth={2} className="text-primary" />
        {t("coachingClassesTitle")}
      </h1>

      <Card>
        <CardContent>
          <form onSubmit={createClass} className="flex flex-wrap items-end gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="class-name">{t("coachingClassesName")}</Label>
              <Input
                id="class-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="h-8 w-40"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="class-starts">{t("coachingClassesStartsAt")}</Label>
              <Input
                id="class-starts"
                type="datetime-local"
                value={startsAt}
                onChange={(e) => setStartsAt(e.target.value)}
                className="h-8"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="class-capacity">{t("coachingClassesCapacity")}</Label>
              <Input
                id="class-capacity"
                type="number"
                value={capacity}
                onChange={(e) => setCapacity(e.target.value)}
                className="h-8 w-20"
              />
            </div>
            <Button type="submit" size="sm">
              {t("coachingClassesCreate")}
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <ul className="space-y-2">
          {classList.map((cls) => (
            <li
              key={cls.id}
              className={`cursor-pointer rounded-xl border p-3 text-sm transition-colors hover:bg-muted/50 ${
                selectedClass === cls.id ? "border-primary bg-primary/5" : ""
              }`}
              onClick={() => setSelectedClass(cls.id)}
            >
              <p className="font-medium">{cls.name}</p>
              <p className="font-dashboard-mono text-muted-foreground">
                {new Date(cls.starts_at).toLocaleString()} &middot; {cls.booked_count}/{cls.capacity}
              </p>
            </li>
          ))}
          {classList.length === 0 && (
            <li className="text-sm text-muted-foreground">{t("coachingClassesEmpty")}</li>
          )}
        </ul>

        {selectedClass && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground">
                <Users size={14} strokeWidth={2} />
                {t("coachingClassesBookings")}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex gap-2">
                <Input
                  placeholder={t("coachingClassesMemberIdPlaceholder")}
                  value={memberIdToBook}
                  onChange={(e) => setMemberIdToBook(e.target.value)}
                  className="h-8"
                />
                <Button size="sm" onClick={book}>
                  {t("coachingClassesBook")}
                </Button>
              </div>
              <ul className="divide-y text-sm">
                {bookingList.map((booking) => (
                  <li key={booking.id} className="flex items-center justify-between py-1.5">
                    <span>
                      {booking.member_name} &middot; <span className="capitalize">{booking.status}</span>
                    </span>
                    {booking.status !== "cancelled" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-1.5 text-xs text-destructive hover:text-destructive"
                        onClick={async () => {
                          await cancelBooking(booking.id);
                          refresh();
                        }}
                      >
                        {t("coachingClassesCancel")}
                      </Button>
                    )}
                  </li>
                ))}
                {bookingList.length === 0 && (
                  <li className="py-1.5 text-muted-foreground">{t("coachingClassesNoBookings")}</li>
                )}
              </ul>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
