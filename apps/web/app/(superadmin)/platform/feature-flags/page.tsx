"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { listFeatureFlags, upsertFeatureFlag } from "@fitkhata/api-client";
import { Flag } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <Flag size={18} strokeWidth={2} className="text-primary" />
        Feature flags
      </h1>

      <Card>
        <CardContent>
          <div className="flex flex-wrap items-end gap-2">
            <div className="space-y-1.5">
              <Label htmlFor="flag-key">Key</Label>
              <Input
                id="flag-key"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder="e.g. ai_insights"
                className="h-8 w-56"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="flag-rollout">Rollout %</Label>
              <Input
                id="flag-rollout"
                value={rolloutPct}
                onChange={(e) => setRolloutPct(e.target.value)}
                placeholder="optional"
                className="h-8 w-28"
              />
            </div>
            <Button size="sm" onClick={create}>
              Add flag
            </Button>
          </div>
        </CardContent>
      </Card>

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
          {query.isLoading &&
            Array.from({ length: 3 }).map((_, i) => (
              <TableRow key={`skeleton-${i}`}>
                <TableCell colSpan={4} className="h-9" />
              </TableRow>
            ))}
          {(query.data ?? []).map((flag) => (
            <TableRow key={flag.id}>
              <TableCell className="font-medium">{flag.key}</TableCell>
              <TableCell>
                <button onClick={() => toggleDefault(flag.key, flag.default)}>
                  <Badge variant={flag.default ? "default" : "secondary"}>
                    {flag.default ? "on" : "off"}
                  </Badge>
                </button>
              </TableCell>
              <TableCell className="font-dashboard-mono">{flag.rollout_pct ?? "-"}</TableCell>
              <TableCell className="font-dashboard-mono">
                {Object.keys(flag.per_org_overrides).length} org(s)
              </TableCell>
            </TableRow>
          ))}
          {!query.isLoading && (query.data ?? []).length === 0 && (
            <TableRow>
              <TableCell colSpan={4} className="py-8 text-center text-sm text-muted-foreground">
                No feature flags yet.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
