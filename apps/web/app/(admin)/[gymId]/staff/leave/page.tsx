"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  approveLeaveRequest,
  listLeaveRequests,
  listStaffProfiles,
  rejectLeaveRequest,
  submitLeaveRequest,
  type LeaveKind,
  type LeaveRequest,
  type StaffProfile,
} from "@fitkhata/api-client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StaffTabs } from "@/components/staff/staff-tabs";

function toList<T>(data: T[] | { results: T[] } | undefined): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : data.results;
}

const KINDS: { value: LeaveKind; label: string }[] = [
  { value: "sick", label: "Sick" },
  { value: "casual", label: "Casual" },
  { value: "festival", label: "Festival" },
  { value: "unpaid", label: "Unpaid" },
  { value: "other", label: "Other" },
];

export default function LeavePage() {
  const queryClient = useQueryClient();
  const [staffId, setStaffId] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [kind, setKind] = useState<LeaveKind>("casual");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const staffQuery = useQuery({ queryKey: ["staff", "profiles"], queryFn: listStaffProfiles });
  const staffList = toList<StaffProfile>(staffQuery.data);

  const pendingQuery = useQuery({
    queryKey: ["staff", "leave-requests", "pending"],
    queryFn: () => listLeaveRequests("pending"),
  });
  const pending = toList<LeaveRequest>(pendingQuery.data);

  function staffLabel(id: string): string {
    const s = staffList.find((p) => p.id === id);
    return s?.full_name ?? s?.badge_code ?? id;
  }

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["staff", "leave-requests"] });
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await submitLeaveRequest({ staff: staffId, from_date: fromDate, to_date: toDate, kind, reason });
      setFromDate("");
      setToDate("");
      setReason("");
      refresh();
    } catch {
      setError("Couldn't submit that leave request.");
    }
  }

  async function approve(id: string) {
    setError(null);
    try {
      await approveLeaveRequest(id);
      refresh();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data
        ?.detail;
      setError(detail ?? "Couldn't approve that request.");
    }
  }

  async function reject(id: string) {
    await rejectLeaveRequest(id);
    refresh();
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">Staff</h1>
      <StaffTabs />

      <form onSubmit={submit} className="flex flex-wrap items-end gap-3 rounded border p-3">
        <div className="space-y-1">
          <Label htmlFor="leave-staff">Staff</Label>
          <select
            id="leave-staff"
            value={staffId}
            onChange={(e) => setStaffId(e.target.value)}
            className="h-9 w-40 rounded border bg-background px-2 text-sm"
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
          <Label htmlFor="leave-from">From</Label>
          <Input id="leave-from" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} required />
        </div>
        <div className="space-y-1">
          <Label htmlFor="leave-to">To</Label>
          <Input id="leave-to" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} required />
        </div>
        <div className="space-y-1">
          <Label htmlFor="leave-kind">Kind</Label>
          <select
            id="leave-kind"
            value={kind}
            onChange={(e) => setKind(e.target.value as LeaveKind)}
            className="h-9 rounded border bg-background px-2 text-sm"
          >
            {KINDS.map((k) => (
              <option key={k.value} value={k.value}>
                {k.label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="leave-reason">Reason</Label>
          <Input id="leave-reason" value={reason} onChange={(e) => setReason(e.target.value)} className="w-40" />
        </div>
        <Button type="submit">Submit</Button>
      </form>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="space-y-2">
        <h2 className="text-lg font-medium">Pending approval</h2>
        <ul className="space-y-2">
          {pending.map((leave) => (
            <li key={leave.id} className="flex items-center justify-between rounded border p-3 text-sm">
              <div>
                <p className="font-medium">{staffLabel(leave.staff)}</p>
                <p className="opacity-70">
                  {leave.kind} &middot; {leave.from_date} to {leave.to_date}
                  {leave.reason && <> &middot; {leave.reason}</>}
                </p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => reject(leave.id)}>
                  Reject
                </Button>
                <Button size="sm" onClick={() => approve(leave.id)}>
                  Approve
                </Button>
              </div>
            </li>
          ))}
          {pending.length === 0 && <li className="text-sm opacity-60">Nothing pending.</li>}
        </ul>
      </div>
    </div>
  );
}
