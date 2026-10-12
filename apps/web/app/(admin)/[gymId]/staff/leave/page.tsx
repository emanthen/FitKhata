"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
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
import { CalendarOff, IdCard, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

export default function LeavePage() {
  const t = useTranslations("admin");
  const queryClient = useQueryClient();
  const KINDS: { value: LeaveKind; label: string }[] = [
    { value: "sick", label: t("staffLeaveKindSick") },
    { value: "casual", label: t("staffLeaveKindCasual") },
    { value: "festival", label: t("staffLeaveKindFestival") },
    { value: "unpaid", label: t("staffLeaveKindUnpaid") },
    { value: "other", label: t("staffLeaveKindOther") },
  ];
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
      setError(t("staffLeaveSubmitError"));
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
      setError(detail ?? t("staffLeaveApproveError"));
    }
  }

  async function reject(id: string) {
    await rejectLeaveRequest(id);
    refresh();
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <IdCard size={18} strokeWidth={2} className="text-primary" />
        {t("staffPageTitle")}
      </h1>
      <StaffTabs />

      <Card>
        <CardContent>
          <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="leave-staff">{t("staffLeaveStaffLabel")}</Label>
              <Select value={staffId} onValueChange={setStaffId}>
                <SelectTrigger id="leave-staff" className="h-8 w-40 text-sm">
                  <SelectValue placeholder={t("staffLeaveChoosePlaceholder")} />
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
              <Label htmlFor="leave-from">{t("staffLeaveFromLabel")}</Label>
              <Input
                id="leave-from"
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="h-8"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="leave-to">{t("staffLeaveToLabel")}</Label>
              <Input
                id="leave-to"
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="h-8"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="leave-kind">{t("staffLeaveKindLabel")}</Label>
              <Select value={kind} onValueChange={(v) => setKind(v as LeaveKind)}>
                <SelectTrigger id="leave-kind" className="h-8 w-32 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {KINDS.map((k) => (
                    <SelectItem key={k.value} value={k.value}>
                      {k.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="leave-reason">{t("staffLeaveReasonLabel")}</Label>
              <Input
                id="leave-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="h-8 w-40"
              />
            </div>
            <Button type="submit" size="sm">
              {t("staffLeaveSubmit")}
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
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground">
            <CalendarOff size={15} strokeWidth={2} />
            {t("staffLeavePendingApproval")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="divide-y">
            {pending.map((leave) => (
              <li key={leave.id} className="flex items-center justify-between py-2.5 text-sm">
                <div>
                  <p className="font-medium">{staffLabel(leave.staff)}</p>
                  <p className="text-muted-foreground">
                    {leave.kind} &middot; {leave.from_date} to {leave.to_date}
                    {leave.reason && <> &middot; {leave.reason}</>}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => reject(leave.id)}>
                    {t("staffLeaveReject")}
                  </Button>
                  <Button size="sm" onClick={() => approve(leave.id)}>
                    {t("staffLeaveApprove")}
                  </Button>
                </div>
              </li>
            ))}
            {pending.length === 0 && (
              <li className="py-2.5 text-sm text-muted-foreground">{t("staffLeaveNothingPending")}</li>
            )}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
