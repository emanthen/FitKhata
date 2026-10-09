"use client";

import { useState } from "react";
import { closeCashShift, openCashShift, type CashShift } from "@fitkhata/api-client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatNpr } from "@/lib/money";

const DENOMINATIONS = ["1000", "500", "100", "50", "20", "10", "5"] as const;

export default function CashShiftPage() {
  const [shift, setShift] = useState<CashShift | null>(null);
  const [openingFloat, setOpeningFloat] = useState("");
  const [counts, setCounts] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [closed, setClosed] = useState<CashShift | null>(null);

  const countedTotal = DENOMINATIONS.reduce(
    (sum, denom) => sum + Number(denom) * Number(counts[denom] || 0),
    0
  );

  async function open(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await openCashShift(openingFloat);
      setShift(result);
    } catch {
      setError("Couldn't open a shift.");
    } finally {
      setSubmitting(false);
    }
  }

  async function close(e: React.FormEvent) {
    e.preventDefault();
    if (!shift) return;
    setError(null);
    setSubmitting(true);
    try {
      const denominations = Object.fromEntries(
        DENOMINATIONS.map((d) => [d, Number(counts[d] || 0)])
      );
      const result = await closeCashShift(shift.id, {
        counted_cash_npr: countedTotal.toFixed(2),
        denominations,
      });
      setClosed(result);
      setShift(null);
    } catch {
      setError("Couldn't close this shift.");
    } finally {
      setSubmitting(false);
    }
  }

  if (closed) {
    const variance = Number(closed.variance_npr);
    return (
      <div className="max-w-md space-y-3">
        <h1 className="text-2xl font-semibold">Shift closed</h1>
        <p className="text-sm">
          Expected {formatNpr(closed.expected_cash_npr, { symbol: true })}, counted{" "}
          {formatNpr(closed.counted_cash_npr ?? "0", { symbol: true })}.
        </p>
        <p
          className={`text-sm font-medium ${
            Math.abs(variance) > 100 ? "text-red-600" : "text-green-700"
          }`}
        >
          Variance: {formatNpr(closed.variance_npr ?? "0", { symbol: true })}
          {Math.abs(variance) > 100 && " — the owner has been notified."}
        </p>
        <Button onClick={() => setClosed(null)}>Open a new shift</Button>
      </div>
    );
  }

  if (!shift) {
    return (
      <div className="max-w-sm space-y-4">
        <h1 className="text-2xl font-semibold">Open a cash shift</h1>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <form onSubmit={open} className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="opening-float">Opening float (NPR)</Label>
            <Input
              id="opening-float"
              type="number"
              step="0.01"
              value={openingFloat}
              onChange={(e) => setOpeningFloat(e.target.value)}
              required
            />
          </div>
          <Button type="submit" disabled={submitting}>
            {submitting ? "..." : "Open shift"}
          </Button>
        </form>
      </div>
    );
  }

  return (
    <div className="max-w-sm space-y-4">
      <h1 className="text-2xl font-semibold">Close cash shift</h1>
      <p className="text-sm opacity-60">
        Opened with {formatNpr(shift.opening_float_npr, { symbol: true })}.
      </p>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <form onSubmit={close} className="space-y-3">
        <div className="space-y-2">
          <Label>Count the drawer</Label>
          {DENOMINATIONS.map((denom) => (
            <div key={denom} className="flex items-center gap-2">
              <span className="w-16 text-sm opacity-70">NPR {denom}</span>
              <span className="opacity-50">×</span>
              <Input
                type="number"
                min="0"
                value={counts[denom] ?? ""}
                onChange={(e) => setCounts((prev) => ({ ...prev, [denom]: e.target.value }))}
                className="h-8 w-20"
              />
            </div>
          ))}
        </div>
        <p className="text-sm font-medium">
          Counted total: {formatNpr(countedTotal.toFixed(2), { symbol: true })}
        </p>
        <Button type="submit" disabled={submitting}>
          {submitting ? "..." : "Close shift"}
        </Button>
      </form>
    </div>
  );
}
