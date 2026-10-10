"use client";

import { useQuery } from "@tanstack/react-query";
import { listAllTickets } from "@fitkhata/api-client";

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
  const query = useQuery({ queryKey: ["platform", "tickets"], queryFn: listAllTickets });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Ticket inbox</h1>
      {query.isLoading ? (
        <p className="text-sm opacity-60">Loading...</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Organization</TableHead>
              <TableHead>Subject</TableHead>
              <TableHead>Priority</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Updated</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
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
                <TableCell>{new Date(ticket.updated_at).toLocaleString()}</TableCell>
              </TableRow>
            ))}
            {(query.data ?? []).length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-sm opacity-60">
                  No tickets.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
