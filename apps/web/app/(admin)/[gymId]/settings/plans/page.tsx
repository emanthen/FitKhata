"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createAddOn, createPlan, listAddOns, listPlans } from "@fitkhata/api-client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatNpr } from "@/lib/money";

export default function PlansSettingsPage() {
  const queryClient = useQueryClient();
  const plans = useQuery({ queryKey: ["plans"], queryFn: listPlans });
  const addons = useQuery({ queryKey: ["addons"], queryFn: listAddOns });

  const [planName, setPlanName] = useState("");
  const [planDays, setPlanDays] = useState("");
  const [planPrice, setPlanPrice] = useState("");
  const [planError, setPlanError] = useState<string | null>(null);

  const [addonName, setAddonName] = useState("");
  const [addonPrice, setAddonPrice] = useState("");
  const [addonKind, setAddonKind] = useState("locker");
  const [addonError, setAddonError] = useState<string | null>(null);

  async function submitPlan(e: React.FormEvent) {
    e.preventDefault();
    setPlanError(null);
    try {
      await createPlan({
        name: planName,
        duration_days: Number(planDays),
        price_npr: planPrice,
        joining_fee_npr: "0",
        access_hours: {},
        pt_sessions: 0,
        max_freeze_days: 0,
        is_active: true,
      });
      setPlanName("");
      setPlanDays("");
      setPlanPrice("");
      queryClient.invalidateQueries({ queryKey: ["plans"] });
    } catch {
      setPlanError("Couldn't create the plan — check the details.");
    }
  }

  async function submitAddon(e: React.FormEvent) {
    e.preventDefault();
    setAddonError(null);
    try {
      await createAddOn({
        name: addonName,
        price_npr: addonPrice,
        kind: addonKind as "locker" | "towel" | "pt" | "diet",
      });
      setAddonName("");
      setAddonPrice("");
      queryClient.invalidateQueries({ queryKey: ["addons"] });
    } catch {
      setAddonError("Couldn't create the add-on — check the details.");
    }
  }

  return (
    <div className="max-w-2xl space-y-8">
      <h1 className="text-2xl font-semibold">Plans &amp; add-ons</h1>

      <section className="space-y-3">
        <h2 className="text-lg font-medium">Membership plans</h2>
        <ul className="space-y-1 text-sm">
          {plans.data?.map((p) => (
            <li key={p.id} className="flex justify-between rounded border px-3 py-2">
              <span>{p.name}</span>
              <span className="opacity-60">
                {formatNpr(p.price_npr, { symbol: true })} / {p.duration_days}d
              </span>
            </li>
          ))}
        </ul>
        {planError && <p className="text-sm text-red-600">{planError}</p>}
        <form onSubmit={submitPlan} className="flex flex-wrap items-end gap-2">
          <div className="space-y-1">
            <Label htmlFor="plan-name">Name</Label>
            <Input id="plan-name" value={planName} onChange={(e) => setPlanName(e.target.value)} required />
          </div>
          <div className="space-y-1">
            <Label htmlFor="plan-days">Duration (days)</Label>
            <Input
              id="plan-days"
              type="number"
              value={planDays}
              onChange={(e) => setPlanDays(e.target.value)}
              className="w-28"
              required
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="plan-price">Price (NPR)</Label>
            <Input
              id="plan-price"
              type="number"
              step="0.01"
              value={planPrice}
              onChange={(e) => setPlanPrice(e.target.value)}
              className="w-32"
              required
            />
          </div>
          <Button type="submit">Add plan</Button>
        </form>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-medium">Add-ons</h2>
        <ul className="space-y-1 text-sm">
          {addons.data?.map((a) => (
            <li key={a.id} className="flex justify-between rounded border px-3 py-2">
              <span>
                {a.name} <span className="opacity-60">({a.kind})</span>
              </span>
              <span className="opacity-60">{formatNpr(a.price_npr, { symbol: true })}</span>
            </li>
          ))}
        </ul>
        {addonError && <p className="text-sm text-red-600">{addonError}</p>}
        <form onSubmit={submitAddon} className="flex flex-wrap items-end gap-2">
          <div className="space-y-1">
            <Label htmlFor="addon-name">Name</Label>
            <Input
              id="addon-name"
              value={addonName}
              onChange={(e) => setAddonName(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="addon-price">Price (NPR)</Label>
            <Input
              id="addon-price"
              type="number"
              step="0.01"
              value={addonPrice}
              onChange={(e) => setAddonPrice(e.target.value)}
              className="w-32"
              required
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="addon-kind">Kind</Label>
            <select
              id="addon-kind"
              value={addonKind}
              onChange={(e) => setAddonKind(e.target.value)}
              className="h-8 rounded border px-2 text-sm"
            >
              <option value="locker">Locker</option>
              <option value="towel">Towel</option>
              <option value="pt">Personal training</option>
              <option value="diet">Diet plan</option>
            </select>
          </div>
          <Button type="submit">Add add-on</Button>
        </form>
      </section>
    </div>
  );
}
