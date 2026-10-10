"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { listFeatureFlags, upsertFeatureFlag } from "@fitkhata/api-client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function FeatureFlagsPage() {
  const query = useQuery({ queryKey: ["platform", "feature-flags"], queryFn: listFeatureFlags });
  const queryClient = useQueryClient();
  const [key, setKey] = useState("");
  const [rolloutPct, setRolloutPct] = useState("");

  async function create() {
    if (!key.trim()) return;
    await upsertFeatureFlag({
      key: key.trim(),
      default: false,
      rollout_pct: rolloutPct ? Number(rolloutPct) : null,
    });
    setKey("");
    setRolloutPct("");
    queryClient.invalidateQueries({ queryKey: ["platform", "feature-flags"] });
  }

  async function toggleDefault(flagKey: string, current: boolean) {
    await upsertFeatureFlag({ key: flagKey, default: !current });
    queryClient.invalidateQueries({ queryKey: ["platform", "feature-flags"] });
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Feature flags</h1>

      <div className="flex items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor="flag-key">Key</Label>
          <Input
            id="flag-key"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="e.g. ai_insights"
            className="w-56"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="flag-rollout">Rollout %</Label>
          <Input
            id="flag-rollout"
            value={rolloutPct}
            onChange={(e) => setRolloutPct(e.target.value)}
            placeholder="optional"
            className="w-28"
          />
        </div>
        <Button onClick={create}>Add flag</Button>
      </div>

      {query.isLoading ? (
        <p className="text-sm opacity-60">Loading...</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Key</TableHead>
              <TableHead>Default</TableHead>
              <TableHead>Rollout %</TableHead>
              <TableHead>Per-org overrides</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(query.data ?? []).map((flag) => (
              <TableRow key={flag.id}>
                <TableCell className="font-medium">{flag.key}</TableCell>
                <TableCell>
                  <button
                    onClick={() => toggleDefault(flag.key, flag.default)}
                    className="rounded border px-2 py-0.5 text-xs"
                  >
                    {flag.default ? "on" : "off"}
                  </button>
                </TableCell>
                <TableCell>{flag.rollout_pct ?? "—"}</TableCell>
                <TableCell>{Object.keys(flag.per_org_overrides).length} org(s)</TableCell>
              </TableRow>
            ))}
            {(query.data ?? []).length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-sm opacity-60">
                  No feature flags yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
