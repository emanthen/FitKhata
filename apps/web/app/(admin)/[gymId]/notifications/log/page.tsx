"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getMonthlyNotificationCost,
  listNotificationLog,
  type Notification as NotificationLogEntry,
  type NotificationChannel,
  type Page,
} from "@fitkhata/api-client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { formatNpr } from "@/lib/money";

const STATUS_FILTERS = ["all", "queued", "sent", "delivered", "failed"] as const;
const CHANNEL_FILTERS: ("all" | NotificationChannel)[] = ["all", "sms", "whatsapp", "push", "email"];

function unwrap(data: NotificationLogEntry[] | Page<NotificationLogEntry> | undefined): NotificationLogEntry[] {
  if (!data) return [];
  return Array.isArray(data) ? data : data.results;
}

export default function NotificationLogPage() {
  const [status, setStatus] = useState<(typeof STATUS_FILTERS)[number]>("all");
  const [channel, setChannel] = useState<"all" | NotificationChannel>("all");

  const log = useQuery({
    queryKey: ["notification-log", status, channel],
    queryFn: () =>
      listNotificationLog({
        status: status === "all" ? undefined : status,
        channel: channel === "all" ? undefined : channel,
      }),
  });
  const monthlyCost = useQuery({
    queryKey: ["notification-log", "monthly-cost"],
    queryFn: getMonthlyNotificationCost,
  });

  const rows = unwrap(log.data);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Delivery log</h1>
        {monthlyCost.data && (
          <p className="text-sm opacity-70">
            This month: {formatNpr(monthlyCost.data.cost_npr, { symbol: true })}
          </p>
        )}
      </div>

      <div className="flex gap-3">
        <Select value={status} onValueChange={(v) => setStatus(v as typeof status)}>
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_FILTERS.map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={channel} onValueChange={(v) => setChannel(v as typeof channel)}>
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CHANNEL_FILTERS.map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Member</TableHead>
            <TableHead>Event</TableHead>
            <TableHead>Channel</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Cost</TableHead>
            <TableHead>When</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((n) => (
            <TableRow key={n.id}>
              <TableCell>{n.member_name}</TableCell>
              <TableCell>{n.template_key || "broadcast"}</TableCell>
              <TableCell className="capitalize">{n.channel}</TableCell>
              <TableCell>
                <Badge variant={n.status === "failed" ? "destructive" : "secondary"}>
                  {n.status}
                </Badge>
              </TableCell>
              <TableCell>{formatNpr(n.cost_npr, { symbol: true })}</TableCell>
              <TableCell className="text-xs opacity-60">
                {new Date(n.created_at).toLocaleString()}
              </TableCell>
            </TableRow>
          ))}
          {rows.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="text-center text-sm opacity-60">
                No notifications match these filters.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
