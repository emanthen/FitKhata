"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createPromoCode, listPromoCodes } from "@fitkhata/api-client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatNpr } from "@/lib/money";

export default function PromoCodesSettingsPage() {
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
      setError("Couldn't create the promo code — check the details.");
    }
  }

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-2xl font-semibold">Promo codes</h1>

      <ul className="space-y-1 text-sm">
        {promoCodes.data?.map((p) => (
          <li key={p.id} className="flex justify-between rounded border px-3 py-2">
            <span className="font-mono">{p.code}</span>
            <span className="opacity-60">
              {p.kind === "flat" ? `${formatNpr(p.value, { symbol: true })} off` : `${p.value}% off`} ·{" "}
              used {p.times_used}
              {p.usage_limit ? `/${p.usage_limit}` : ""}
            </span>
          </li>
        ))}
      </ul>

      {error && <p className="text-sm text-red-600">{error}</p>}
      <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor="promo-code">Code</Label>
          <Input
            id="promo-code"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            required
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="promo-kind">Kind</Label>
          <select
            id="promo-kind"
            value={kind}
            onChange={(e) => setKind(e.target.value as "flat" | "percent")}
            className="h-8 rounded border px-2 text-sm"
          >
            <option value="flat">Flat (NPR)</option>
            <option value="percent">Percent</option>
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="promo-value">Value</Label>
          <Input
            id="promo-value"
            type="number"
            step="0.01"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="w-28"
            required
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="promo-from">Valid from</Label>
          <Input
            id="promo-from"
            type="date"
            value={validFrom}
            onChange={(e) => setValidFrom(e.target.value)}
            required
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="promo-to">Valid to</Label>
          <Input
            id="promo-to"
            type="date"
            value={validTo}
            onChange={(e) => setValidTo(e.target.value)}
            required
          />
        </div>
        <Button type="submit">Add promo code</Button>
      </form>
    </div>
  );
}
