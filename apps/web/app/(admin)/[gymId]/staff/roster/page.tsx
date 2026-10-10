"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createStaffShift,
  listStaffProfiles,
  listStaffShifts,
  type ShiftConflictError,
  type StaffProfile,
  type StaffShift,
} from "@fitkhata/api-client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StaffTabs } from "@/components/staff/staff-tabs";

function toList<T>(data: T[] | { results: T[] } | undefined): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : data.results;
}

export default function RosterPage() {
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
        setError("Couldn't create that shift.");
      }
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold">Staff</h1>
      <StaffTabs />

      <form onSubmit={submit} className="flex flex-wrap items-end gap-3 rounded border p-3">
        <div className="space-y-1">
          <Label htmlFor="roster-staff">Staff</Label>
          <select
            id="roster-staff"
            value={staffId}
            onChange={(e) => setStaffId(e.target.value)}
            className="h-9 w-48 rounded border bg-background px-2 text-sm"
            required
          >
            <option value="" disabled>
              Choose...
            </option>
            {staffList.map((s) => (
              <option key={s.id} value={s.id}>
                {s.full_name || s.badge_code}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="roster-date">Date</Label>
          <Input
            id="roster-date"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            required
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="roster-start">Start</Label>
          <Input
            id="roster-start"
            type="time"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className="w-28"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="roster-end">End</Label>
          <Input
            id="roster-end"
            type="time"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            className="w-28"
          />
        </div>
        <Button type="submit">Add shift</Button>
      </form>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <ul className="space-y-1">
        {shifts.map((shift) => (
          <li
            key={shift.id}
            className="flex items-center justify-between rounded border px-3 py-1.5 text-sm"
          >
            <span>{staffLabel(shift.staff)}</span>
            <span className="opacity-70">
              {shift.date} &middot; {shift.start}&ndash;{shift.end}
            </span>
          </li>
        ))}
        {shifts.length === 0 && <li className="text-sm opacity-60">No shifts scheduled.</li>}
      </ul>
    </div>
  );
}
