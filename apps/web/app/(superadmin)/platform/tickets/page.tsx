"use client";

import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { listAllTickets } from "@fitkhata/api-client";
import { LifeBuoy } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const PRIORITY_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  low: "outline",
  medium: "secondary",
  high: "default",
  urgent: "destructive",
};

export default function TicketInboxPage() {
  const t = useTranslations("admin");
  const query = useQuery({ queryKey: ["platform", "tickets"], queryFn: listAllTickets });

  return (
    <div className="space-y-6">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <LifeBuoy size={18} strokeWidth={2} className="text-primary" />
        {t("platformTicketsTitle")}
      </h1>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t("platformTicketsColOrg")}</TableHead>
            <TableHead>{t("platformTicketsColSubject")}</TableHead>
            <TableHead>{t("platformTicketsColPriority")}</TableHead>
            <TableHead>{t("platformTicketsColStatus")}</TableHead>
            <TableHead>{t("platformTicketsColUpdated")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {query.isLoading &&
            Array.from({ length: 4 }).map((_, i) => (
              <TableRow key={`skeleton-${i}`}>
                <TableCell colSpan={5} className="h-9" />
              </TableRow>
            ))}
          {(query.data ?? []).map((ticket) => (
            <TableRow key={ticket.id}>
              <TableCell>{ticket.org__name}</TableCell>
              <TableCell className="font-medium">{ticket.subject}</TableCell>
              <TableCell>
                <Badge variant={PRIORITY_VARIANT[ticket.priority] ?? "outline"}>
                  {ticket.priority}
                </Badge>
              </TableCell>
              <TableCell className="capitalize">{ticket.status}</TableCell>
              <TableCell className="font-dashboard-mono text-xs text-muted-foreground">
                {new Date(ticket.updated_at).toLocaleString()}
              </TableCell>
            </TableRow>
          ))}
          {!query.isLoading && (query.data ?? []).length === 0 && (
            <TableRow>
              <TableCell colSpan={5} className="py-8 text-center text-sm text-muted-foreground">
                {t("platformTicketsEmpty")}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
