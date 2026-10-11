"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { impersonate, listTenants, tokenStore } from "@fitkhata/api-client";
import { Building2, UserCog } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { redirectAfterAuth } from "@/lib/auth";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatNpr } from "@/lib/money";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  trial: "secondary",
  active: "default",
  grace: "outline",
  read_only: "destructive",
  suspended: "destructive",
  cancelled: "outline",
};

export default function TenantsPage() {
  const query = useQuery({ queryKey: ["platform", "tenants"], queryFn: listTenants });
  const [target, setTarget] = useState<{ orgId: string; orgName: string } | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  async function confirmImpersonate() {
    if (!target) return;
    if (!reason.trim()) {
      setError("A reason is required.");
      return;
    }
    try {
      const result = await impersonate(target.orgId, reason.trim());
      // Deliberately no queryClient.invalidateQueries() here — it would
      // refetch still-mounted platform-only queries (this very page)
      // using the new, non-platform-staff token and 403 before the
      // navigation below completes. A full navigation starts fresh.
      tokenStore.beginImpersonation(result.access);
      await redirectAfterAuth((path) => {
        window.location.href = path;
      });
    } catch {
      setError("Could not start impersonation — the org may have no active owner.");
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <Building2 size={18} strokeWidth={2} className="text-primary" />
        Tenants
      </h1>
      {query.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Organization</TableHead>
                <TableHead>Plan</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">MRR</TableHead>
                <TableHead className="text-right">Members</TableHead>
                <TableHead>Last active</TableHead>
                <TableHead className="text-right">Health</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {(query.data ?? []).map((row) => (
                <TableRow key={row.org_id}>
                  <TableCell className="font-medium">{row.org_name}</TableCell>
                  <TableCell className="capitalize">{row.plan_code}</TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[row.status] ?? "outline"}>{row.status}</Badge>
                  </TableCell>
                  <TableCell className="font-dashboard-mono text-right">{formatNpr(row.mrr_npr)}</TableCell>
                  <TableCell className="font-dashboard-mono text-right">{row.member_count}</TableCell>
                  <TableCell className="font-dashboard-mono text-xs text-muted-foreground">
                    {row.last_active_at ? new Date(row.last_active_at).toLocaleDateString() : "-"}
                  </TableCell>
                  <TableCell className="font-dashboard-mono text-right">{row.health_score}</TableCell>
                  <TableCell>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setTarget({ orgId: row.org_id, orgName: row.org_name });
                        setReason("");
                        setError("");
                      }}
                    >
                      <UserCog size={13} strokeWidth={2} data-icon="inline-start" />
                      Impersonate
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog open={target !== null} onOpenChange={(open) => !open && setTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Impersonate {target?.orgName}</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="reason">Reason (required, audited)</Label>
            <Input
              id="reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. investigating a billing issue"
            />
            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTarget(null)}>
              Cancel
            </Button>
            <Button onClick={confirmImpersonate}>Start (30 min)</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
