"use client";

import { useQuery } from "@tanstack/react-query";
import { listLeads } from "@fitkhata/api-client";
import { UserPlus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  new: "default",
  contacted: "secondary",
  converted: "default",
  lost: "outline",
};

export default function LeadsPage() {
  const query = useQuery({ queryKey: ["platform", "leads"], queryFn: listLeads });

  return (
    <div className="space-y-6">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <UserPlus size={18} strokeWidth={2} className="text-primary" />
        Leads
      </h1>
      <p className="text-sm text-muted-foreground">
        Captured from Facebook Lead Ads. This is a flat log, not a pipeline — Meta's webhook only
        delivers a <code className="font-dashboard-mono">leadgen_id</code>, so follow up in Meta's
        own Lead Ads form response list for the full contact details until a Graph API lookup is
        wired up here.
      </p>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Phone</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Source</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Captured</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {query.isLoading &&
            Array.from({ length: 3 }).map((_, i) => (
              <TableRow key={`skeleton-${i}`}>
                <TableCell colSpan={6} className="h-9" />
              </TableRow>
            ))}
          {(query.data ?? []).map((lead) => (
            <TableRow key={lead.id}>
              <TableCell className="font-medium">{lead.full_name || "—"}</TableCell>
              <TableCell className="font-dashboard-mono">{lead.phone || "—"}</TableCell>
              <TableCell>{lead.email || "—"}</TableCell>
              <TableCell className="text-muted-foreground">{lead.source}</TableCell>
              <TableCell>
                <Badge variant={STATUS_VARIANT[lead.status] ?? "secondary"}>{lead.status}</Badge>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {new Date(lead.created_at).toLocaleString()}
              </TableCell>
            </TableRow>
          ))}
          {!query.isLoading && (query.data ?? []).length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="py-8 text-center text-sm text-muted-foreground">
                No leads captured yet.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
