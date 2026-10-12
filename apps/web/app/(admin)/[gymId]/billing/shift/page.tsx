"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { closeCashShift, openCashShift, type CashShift } from "@fitkhata/api-client";
import { CircleCheck, TriangleAlert, Wallet } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatNpr } from "@/lib/money";

const DENOMINATIONS = ["1000", "500", "100", "50", "20", "10", "5"] as const;

export default function CashShiftPage() {
  const t = useTranslations("admin");
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
      setError(t("billingShiftOpenError"));
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
      setError(t("billingShiftCloseError"));
    } finally {
      setSubmitting(false);
    }
  }

  if (closed) {
    const variance = Number(closed.variance_npr);
    const flagged = Math.abs(variance) > 100;
    return (
      <div className="max-w-md space-y-4">
        <h1 className="text-xl font-semibold tracking-tight">{t("billingShiftClosedTitle")}</h1>
        <Card>
          <CardContent className="space-y-2">
            <p className="font-dashboard-mono text-sm">
              {t("billingShiftExpectedCounted", {
                expected: formatNpr(closed.expected_cash_npr, { symbol: true }),
                counted: formatNpr(closed.counted_cash_npr ?? "0", { symbol: true }),
              })}
            </p>
            <p
              className={`font-dashboard-mono flex items-center gap-1.5 text-sm font-medium ${
                flagged ? "text-destructive" : "text-foreground"
              }`}
            >
              {flagged ? (
                <TriangleAlert size={14} strokeWidth={2} />
              ) : (
                <CircleCheck size={14} strokeWidth={2} />
              )}
              {t("billingShiftVarianceLabel", {
                variance: formatNpr(closed.variance_npr ?? "0", { symbol: true }),
              })}
              {flagged && (
                <span className="font-sans font-normal"> {t("billingShiftOwnerNotified")}</span>
              )}
            </p>
          </CardContent>
        </Card>
        <Button onClick={() => setClosed(null)}>{t("billingShiftOpenNewButton")}</Button>
      </div>
    );
  }

  if (!shift) {
    return (
      <div className="max-w-sm space-y-4">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <Wallet size={18} strokeWidth={2} className="text-primary" />
          {t("billingShiftOpenTitle")}
        </h1>
        {error && (
          <p className="flex items-center gap-1.5 text-sm text-destructive">
            <TriangleAlert size={14} strokeWidth={2} />
            {error}
          </p>
        )}
        <form onSubmit={open} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="opening-float">{t("billingShiftOpeningFloatLabel")}</Label>
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
            {submitting ? "..." : t("billingShiftOpenButton")}
          </Button>
        </form>
      </div>
    );
  }

  return (
    <div className="max-w-sm space-y-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{t("billingShiftCloseTitle")}</h1>
        <p className="font-dashboard-mono mt-0.5 text-sm text-muted-foreground">
          {t("billingShiftOpenedWith", {
            amount: formatNpr(shift.opening_float_npr, { symbol: true }),
          })}
        </p>
      </div>
      {error && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <TriangleAlert size={14} strokeWidth={2} />
          {error}
        </p>
      )}

      <Card>
        <CardContent>
          <form onSubmit={close} className="space-y-3">
            <div className="space-y-2">
              <Label>{t("billingShiftCountDrawerLabel")}</Label>
              {DENOMINATIONS.map((denom) => (
                <div key={denom} className="flex items-center gap-2">
                  <span className="font-dashboard-mono w-16 text-sm text-muted-foreground">
                    NPR {denom}
                  </span>
                  <span className="text-muted-foreground">&times;</span>
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
            <p className="font-dashboard-mono border-t pt-3 text-sm font-medium">
              {t("billingShiftCountedTotal", {
                total: formatNpr(countedTotal.toFixed(2), { symbol: true }),
              })}
            </p>
            <Button type="submit" disabled={submitting}>
              {submitting ? "..." : t("billingShiftCloseButton")}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
