"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createStaffShift,
  listStaffProfiles,
  listStaffShifts,
  type ShiftConflictError,
  type StaffProfile,
  type StaffShift,
} from "@fitkhata/api-client";
import { CalendarClock, IdCard, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StaffTabs } from "@/components/staff/staff-tabs";

function toList<T>(data: T[] | { results: T[] } | undefined): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : data.results;
}

export default function RosterPage() {
  const t = useTranslations("admin");
  const queryClient = useQueryClient();
  const [staffId, setStaffId] = useState("");
  const [date, setDate] = useState("");
  const [start, setStart] = useState("09:00");
  const [end, setEnd] = useState("17:00");
  const [error, setError] = useState<string | null>(null);

  const staffQuery = useQuery({ queryKey: ["staff", "profiles"], queryFn: listStaffProfiles });
  const staffList = toList<StaffProfile>(staffQuery.data);

  const shiftsQuery = useQuery({ queryKey: ["staff", "shifts"], queryFn: listStaffShifts });
  const shifts = toList<StaffShift>(shiftsQuery.data).sort((a, b) =>
    a.date === b.date ? a.start.localeCompare(b.start) : a.date.localeCompare(b.date)
  );

  function staffLabel(id: string): string {
    const s = staffList.find((p) => p.id === id);
    return s?.full_name ?? s?.badge_code ?? id;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createStaffShift({ staff: staffId, date, start, end });
      queryClient.invalidateQueries({ queryKey: ["staff", "shifts"] });
    } catch (err: unknown) {
      const data = (err as { response?: { data?: ShiftConflictError } })?.response?.data;
      if (data?.conflicting_shift_id) {
        setError(data.detail);
      } else {
        setError(t("staffRosterCreateError"));
      }
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <IdCard size={18} strokeWidth={2} className="text-primary" />
        {t("staffPageTitle")}
      </h1>
      <StaffTabs />

      <Card>
        <CardContent>
          <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="roster-staff">{t("staffRosterStaffLabel")}</Label>
              <Select value={staffId} onValueChange={setStaffId}>
                <SelectTrigger id="roster-staff" className="h-8 w-48 text-sm">
                  <SelectValue placeholder={t("staffRosterChoosePlaceholder")} />
                </SelectTrigger>
                <SelectContent>
                  {staffList.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.full_name || s.badge_code}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="roster-date">{t("staffRosterDateLabel")}</Label>
              <Input
                id="roster-date"
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="h-8"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="roster-start">{t("staffRosterStartLabel")}</Label>
              <Input
                id="roster-start"
                type="time"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                className="h-8 w-28"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="roster-end">{t("staffRosterEndLabel")}</Label>
              <Input
                id="roster-end"
                type="time"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                className="h-8 w-28"
              />
            </div>
            <Button type="submit" size="sm">
              {t("staffRosterAddShift")}
            </Button>
          </form>
        </CardContent>
      </Card>
      {error && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <TriangleAlert size={14} strokeWidth={2} />
          {error}
        </p>
      )}

      <Card>
        <CardContent>
          <ul className="divide-y">
            {shifts.map((shift) => (
              <li key={shift.id} className="flex items-center justify-between py-2 text-sm">
                <span>{staffLabel(shift.staff)}</span>
                <span className="font-dashboard-mono flex items-center gap-1.5 text-muted-foreground">
                  <CalendarClock size={13} strokeWidth={2} />
                  {shift.date} &middot; {shift.start}&ndash;{shift.end}
                </span>
              </li>
            ))}
            {shifts.length === 0 && (
              <li className="py-2 text-sm text-muted-foreground">{t("staffRosterEmpty")}</li>
            )}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
