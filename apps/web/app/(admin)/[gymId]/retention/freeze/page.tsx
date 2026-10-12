"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  confirmBulkFreeze,
  listFreezeHistory,
  previewFreeze,
  revertFreezeBatch,
  type FreezePreviewRow,
  type FreezeReason,
  type MembershipFreeze,
} from "@fitkhata/api-client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Snowflake, TriangleAlert } from "lucide-react";

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

const REASON_KEYS: Record<FreezeReason, string> = {
  dashain: "retentionReasonDashain",
  tihar: "retentionReasonTihar",
  chhath: "retentionReasonChhath",
  travel: "retentionReasonTravel",
  injury: "retentionReasonInjury",
  other: "retentionReasonOther",
};
const REASONS: FreezeReason[] = ["dashain", "tihar", "chhath", "travel", "injury", "other"];

function groupByBatch(freezes: MembershipFreeze[]): Map<string, MembershipFreeze[]> {
  const groups = new Map<string, MembershipFreeze[]>();
  for (const freeze of freezes) {
    const list = groups.get(freeze.batch_id) ?? [];
    list.push(freeze);
    groups.set(freeze.batch_id, list);
  }
  return groups;
}

export default function FreezeWizardPage() {
  const t = useTranslations("admin");
  const queryClient = useQueryClient();
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState<FreezeReason>("dashain");
  const [preview, setPreview] = useState<{ count: number; rows: FreezePreviewRow[] } | null>(
    null
  );
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const history = useQuery({
    queryKey: ["retention", "freeze-history"],
    queryFn: () => listFreezeHistory(),
  });

  function inputsChangedSincePreview() {
    setPreview(null);
  }

  async function runPreview(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const result = await previewFreeze(startDate, endDate, reason);
      setPreview(result);
    } catch {
      setError(t("retentionPreviewError"));
    }
  }

  async function confirm() {
    setConfirming(true);
    setError(null);
    try {
      await confirmBulkFreeze(startDate, endDate, reason);
      setPreview(null);
      setStartDate("");
      setEndDate("");
      queryClient.invalidateQueries({ queryKey: ["retention", "freeze-history"] });
    } catch {
      setError(t("retentionConfirmError"));
    } finally {
      setConfirming(false);
    }
  }

  async function undo(batchId: string) {
    try {
      await revertFreezeBatch(batchId);
      queryClient.invalidateQueries({ queryKey: ["retention", "freeze-history"] });
    } catch {
      setError(t("retentionUndoError"));
    }
  }

  const batches = groupByBatch(history.data ?? []);

  return (
    <div className="max-w-2xl space-y-6">
      <div className="space-y-4">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <Snowflake size={18} strokeWidth={2} className="text-primary" />
          {t("retentionFreezeWizardTitle")}
        </h1>
        <form onSubmit={runPreview} className="flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="freeze-start">{t("retentionStartDate")}</Label>
            <Input
              id="freeze-start"
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                inputsChangedSincePreview();
              }}
              required
              className="h-8 w-40"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="freeze-end">{t("retentionEndDate")}</Label>
            <Input
              id="freeze-end"
              type="date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                inputsChangedSincePreview();
              }}
              required
              className="h-8 w-40"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="freeze-reason">{t("retentionReason")}</Label>
            <Select
              value={reason}
              onValueChange={(v) => {
                setReason(v as FreezeReason);
                inputsChangedSincePreview();
              }}
            >
              <SelectTrigger id="freeze-reason" className="h-8 w-36 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {REASONS.map((r) => (
                  <SelectItem key={r} value={r}>
                    {t(REASON_KEYS[r])}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button type="submit" size="sm">
            {t("retentionPreview")}
          </Button>
        </form>

        {error && (
          <p className="flex items-center gap-1.5 text-sm text-destructive">
            <TriangleAlert size={14} strokeWidth={2} />
            {error}
          </p>
        )}

        {preview && (
          <Card>
            <CardContent className="space-y-2">
              <p className="text-sm font-medium">
                {t("retentionActiveMembershipsWillFreeze", { count: preview.count })}
              </p>
              <ul className="max-h-64 space-y-1 overflow-y-auto text-sm">
                {preview.rows.map((row) => (
                  <li key={row.membership_id} className="flex justify-between">
                    <span>
                      {row.member_name}
                      {row.would_exceed_max && (
                        <span className="ml-1 text-accent">{t("retentionExceedsMaxFreezeDays")}</span>
                      )}
                    </span>
                    <span className="font-dashboard-mono text-muted-foreground">
                      {row.previous_expiry} &rarr; {row.new_expiry}
                    </span>
                  </li>
                ))}
              </ul>
              <Button onClick={confirm} disabled={confirming} size="sm">
                {confirming ? "..." : t("retentionConfirmFreeze")}
              </Button>
            </CardContent>
          </Card>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-muted-foreground">{t("retentionFreezeHistory")}</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="divide-y">
            {Array.from(batches.entries()).map(([batchId, freezes]) => {
              const allReverted = freezes.every((f) => f.reverted_at);
              return (
                <li key={batchId} className="flex items-center justify-between py-2.5 text-sm">
                  <span className="font-medium">
                    {t("retentionBatchSummary", {
                      reason: freezes[0].reason,
                      count: freezes.length,
                      start: freezes[0].start_date,
                      end: freezes[0].end_date,
                    })}
                  </span>
                  {!allReverted && (
                    <Button variant="outline" size="sm" onClick={() => undo(batchId)} className="h-7 text-xs">
                      {t("retentionUndo")}
                    </Button>
                  )}
                  {allReverted && <span className="text-xs text-muted-foreground">{t("retentionReverted")}</span>}
                </li>
              );
            })}
            {batches.size === 0 && (
              <li className="py-2.5 text-sm text-muted-foreground">{t("retentionNoFreezesYet")}</li>
            )}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
