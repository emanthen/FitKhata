"use client";

import { useState } from "react";
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

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const REASONS: { value: FreezeReason; label: string }[] = [
  { value: "dashain", label: "Dashain" },
  { value: "tihar", label: "Tihar" },
  { value: "chhath", label: "Chhath" },
  { value: "travel", label: "Travel" },
  { value: "injury", label: "Injury" },
  { value: "other", label: "Other" },
];

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
      setError("Couldn't preview this freeze.");
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
      setError("Couldn't confirm this freeze.");
    } finally {
      setConfirming(false);
    }
  }

  async function undo(batchId: string) {
    try {
      await revertFreezeBatch(batchId);
      queryClient.invalidateQueries({ queryKey: ["retention", "freeze-history"] });
    } catch {
      setError("Couldn't undo this batch.");
    }
  }

  const batches = groupByBatch(history.data ?? []);

  return (
    <div className="max-w-2xl space-y-8">
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Festival freeze wizard</h1>
        <form onSubmit={runPreview} className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <Label htmlFor="freeze-start">Start date</Label>
            <Input
              id="freeze-start"
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                inputsChangedSincePreview();
              }}
              required
              className="w-40"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="freeze-end">End date</Label>
            <Input
              id="freeze-end"
              type="date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                inputsChangedSincePreview();
              }}
              required
              className="w-40"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="freeze-reason">Reason</Label>
            <select
              id="freeze-reason"
              className="h-9 w-36 rounded border px-2 text-sm"
              value={reason}
              onChange={(e) => {
                setReason(e.target.value as FreezeReason);
                inputsChangedSincePreview();
              }}
            >
              {REASONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>
          <Button type="submit">Preview</Button>
        </form>

        {error && <p className="text-sm text-red-600">{error}</p>}

        {preview && (
          <div className="space-y-2 rounded border p-3">
            <p className="text-sm font-medium">
              {preview.count} active membership{preview.count === 1 ? "" : "s"} will be frozen.
            </p>
            <ul className="max-h-64 space-y-1 overflow-y-auto text-sm">
              {preview.rows.map((row) => (
                <li key={row.membership_id} className="flex justify-between">
                  <span>
                    {row.member_name}
                    {row.would_exceed_max && (
                      <span className="ml-1 text-amber-600">(exceeds max freeze days)</span>
                    )}
                  </span>
                  <span className="opacity-70">
                    {row.previous_expiry} &rarr; {row.new_expiry}
                  </span>
                </li>
              ))}
            </ul>
            <Button onClick={confirm} disabled={confirming}>
              {confirming ? "..." : "Confirm freeze"}
            </Button>
          </div>
        )}
      </div>

      <div className="space-y-2">
        <h2 className="text-lg font-medium">Freeze history</h2>
        <ul className="space-y-2">
          {Array.from(batches.entries()).map(([batchId, freezes]) => {
            const allReverted = freezes.every((f) => f.reverted_at);
            return (
              <li key={batchId} className="rounded border p-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-medium">
                    {freezes[0].reason} &middot; {freezes.length} membership
                    {freezes.length === 1 ? "" : "s"} &middot; {freezes[0].start_date} to{" "}
                    {freezes[0].end_date}
                  </span>
                  {!allReverted && (
                    <Button variant="outline" onClick={() => undo(batchId)} className="h-7 text-xs">
                      Undo
                    </Button>
                  )}
                  {allReverted && <span className="text-xs opacity-60">Reverted</span>}
                </div>
              </li>
            );
          })}
          {batches.size === 0 && <li className="text-sm opacity-60">No freezes yet.</li>}
        </ul>
      </div>
    </div>
  );
}
