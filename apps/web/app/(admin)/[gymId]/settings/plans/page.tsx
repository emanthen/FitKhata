"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createAddOn, createPlan, listAddOns, listPlans } from "@fitkhata/api-client";
import { PackagePlus, Ticket } from "lucide-react";

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
    <div className="max-w-2xl space-y-6">
      <h1 className="text-xl font-semibold tracking-tight">Plans &amp; add-ons</h1>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Ticket size={16} strokeWidth={2} className="text-primary" />
            Membership plans
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <ul className="divide-y">
            {plans.data?.map((p) => (
              <li key={p.id} className="flex items-center justify-between py-2 text-sm">
                <span>{p.name}</span>
                <span className="font-dashboard-mono text-muted-foreground">
                  {formatNpr(p.price_npr, { symbol: true })} / {p.duration_days}d
                </span>
              </li>
            ))}
            {plans.data?.length === 0 && (
              <li className="py-2 text-sm text-muted-foreground">No plans yet.</li>
            )}
          </ul>
          {planError && <p className="text-sm text-destructive">{planError}</p>}
          <form onSubmit={submitPlan} className="flex flex-wrap items-end gap-2 border-t pt-3">
            <div className="space-y-1.5">
              <Label htmlFor="plan-name">Name</Label>
              <Input
                id="plan-name"
                value={planName}
                onChange={(e) => setPlanName(e.target.value)}
                className="h-8"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="plan-days">Duration (days)</Label>
              <Input
                id="plan-days"
                type="number"
                value={planDays}
                onChange={(e) => setPlanDays(e.target.value)}
                className="h-8 w-28"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="plan-price">Price (NPR)</Label>
              <Input
                id="plan-price"
                type="number"
                step="0.01"
                value={planPrice}
                onChange={(e) => setPlanPrice(e.target.value)}
                className="h-8 w-32"
                required
              />
            </div>
            <Button type="submit" size="sm">
              Add plan
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <PackagePlus size={16} strokeWidth={2} className="text-primary" />
            Add-ons
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <ul className="divide-y">
            {addons.data?.map((a) => (
              <li key={a.id} className="flex items-center justify-between py-2 text-sm">
                <span>
                  {a.name} <span className="text-muted-foreground">({a.kind})</span>
                </span>
                <span className="font-dashboard-mono text-muted-foreground">
                  {formatNpr(a.price_npr, { symbol: true })}
                </span>
              </li>
            ))}
            {addons.data?.length === 0 && (
              <li className="py-2 text-sm text-muted-foreground">No add-ons yet.</li>
            )}
          </ul>
          {addonError && <p className="text-sm text-destructive">{addonError}</p>}
          <form onSubmit={submitAddon} className="flex flex-wrap items-end gap-2 border-t pt-3">
            <div className="space-y-1.5">
              <Label htmlFor="addon-name">Name</Label>
              <Input
                id="addon-name"
                value={addonName}
                onChange={(e) => setAddonName(e.target.value)}
                className="h-8"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="addon-price">Price (NPR)</Label>
              <Input
                id="addon-price"
                type="number"
                step="0.01"
                value={addonPrice}
                onChange={(e) => setAddonPrice(e.target.value)}
                className="h-8 w-32"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="addon-kind">Kind</Label>
              <Select value={addonKind} onValueChange={setAddonKind}>
                <SelectTrigger id="addon-kind" className="h-8 w-40 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="locker">Locker</SelectItem>
                  <SelectItem value="towel">Towel</SelectItem>
                  <SelectItem value="pt">Personal training</SelectItem>
                  <SelectItem value="diet">Diet plan</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button type="submit" size="sm">
              Add add-on
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
