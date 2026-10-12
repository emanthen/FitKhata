"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createPromoCode, listPromoCodes } from "@fitkhata/api-client";
import { Tag } from "lucide-react";

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
import { formatNpr } from "@/lib/money";

export default function PromoCodesSettingsPage() {
  const t = useTranslations("admin");
  const queryClient = useQueryClient();
  const promoCodes = useQuery({ queryKey: ["promo-codes"], queryFn: listPromoCodes });

  const [code, setCode] = useState("");
  const [kind, setKind] = useState<"flat" | "percent">("flat");
  const [value, setValue] = useState("");
  const [validFrom, setValidFrom] = useState("");
  const [validTo, setValidTo] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createPromoCode({
        code,
        kind,
        value,
        valid_from: validFrom,
        valid_to: validTo,
        usage_limit: null,
        per_member_once: true,
      });
      setCode("");
      setValue("");
      setValidFrom("");
      setValidTo("");
      queryClient.invalidateQueries({ queryKey: ["promo-codes"] });
    } catch {
      setError(t("billingPromoCreateError"));
    }
  }

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">{t("settingsPromoCodes")}</h1>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Tag size={16} strokeWidth={2} className="text-primary" />
            {t("billingPromoActiveCodesTitle")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <ul className="divide-y">
            {promoCodes.data?.map((p) => (
              <li key={p.id} className="flex items-center justify-between py-2 text-sm">
                <span className="font-dashboard-mono">{p.code}</span>
                <span className="text-muted-foreground">
                  {p.kind === "flat"
                    ? t("billingPromoOffFlat", { amount: formatNpr(p.value, { symbol: true }) })
                    : t("billingPromoOffPercent", { percent: p.value })}{" "}
                  &middot; {t("billingPromoUsedCount", { count: p.times_used })}
                  {p.usage_limit ? `/${p.usage_limit}` : ""}
                </span>
              </li>
            ))}
            {promoCodes.data?.length === 0 && (
              <li className="py-2 text-sm text-muted-foreground">{t("billingPromoEmptyState")}</li>
            )}
          </ul>

          {error && <p className="text-sm text-destructive">{error}</p>}
          <form onSubmit={submit} className="flex flex-wrap items-end gap-2 border-t pt-3">
            <div className="space-y-1.5">
              <Label htmlFor="promo-code">{t("billingPromoCodeLabel")}</Label>
              <Input
                id="promo-code"
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                className="h-8"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="promo-kind">{t("billingAddonKindLabel")}</Label>
              <Select value={kind} onValueChange={(v) => setKind(v as "flat" | "percent")}>
                <SelectTrigger id="promo-kind" className="h-8 w-36 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="flat">{t("billingPromoKindFlat")}</SelectItem>
                  <SelectItem value="percent">{t("billingPromoKindPercent")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="promo-value">{t("billingPromoValueLabel")}</Label>
              <Input
                id="promo-value"
                type="number"
                step="0.01"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                className="h-8 w-28"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="promo-from">{t("billingPromoValidFromLabel")}</Label>
              <Input
                id="promo-from"
                type="date"
                value={validFrom}
                onChange={(e) => setValidFrom(e.target.value)}
                className="h-8"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="promo-to">{t("billingPromoValidToLabel")}</Label>
              <Input
                id="promo-to"
                type="date"
                value={validTo}
                onChange={(e) => setValidTo(e.target.value)}
                className="h-8"
                required
              />
            </div>
            <Button type="submit" size="sm">
              {t("billingAddPromoCodeButton")}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
