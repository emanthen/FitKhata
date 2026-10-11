"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createDietPlan,
  listDietPlans,
  listFoodItems,
  type DietPlanMealItem,
} from "@fitkhata/api-client";
import { Apple, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const selectClass =
  "h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

function computeTotals(
  items: DietPlanMealItem[],
  foodItems: { id: string; kcal_per_100g: string; protein_g_per_100g: string }[]
) {
  let kcal = 0;
  let protein = 0;
  for (const item of items) {
    const food = foodItems.find((f) => f.id === item.food_item_id);
    if (!food) continue;
    const factor = item.grams / 100;
    kcal += Number(food.kcal_per_100g) * factor;
    protein += Number(food.protein_g_per_100g) * factor;
  }
  return { kcal: Math.round(kcal), protein: Math.round(protein * 10) / 10 };
}

export default function DietPlanBuilderPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [items, setItems] = useState<DietPlanMealItem[]>([]);
  const [saving, setSaving] = useState(false);

  const plans = useQuery({ queryKey: ["coaching", "diet-plans"], queryFn: listDietPlans });
  const foodItemsQuery = useQuery({ queryKey: ["coaching", "food-items"], queryFn: listFoodItems });
  const planList = Array.isArray(plans.data) ? plans.data : plans.data?.results ?? [];
  const foodItemList = Array.isArray(foodItemsQuery.data)
    ? foodItemsQuery.data
    : foodItemsQuery.data?.results ?? [];

  const totals = computeTotals(items, foodItemList);

  function addItem() {
    if (foodItemList.length === 0) return;
    setItems((prev) => [...prev, { food_item_id: foodItemList[0].id, grams: 100 }]);
  }

  function updateItem(index: number, patch: Partial<DietPlanMealItem>) {
    setItems((prev) => prev.map((it, i) => (i === index ? { ...it, ...patch } : it)));
  }

  function removeItem(index: number) {
    setItems((prev) => prev.filter((_, i) => i !== index));
  }

  async function save() {
    setSaving(true);
    try {
      await createDietPlan({
        name,
        kcal_target: totals.kcal,
        protein_g: String(totals.protein),
        meals: [{ meal: "main", items }],
      });
      setName("");
      setItems([]);
      queryClient.invalidateQueries({ queryKey: ["coaching", "diet-plans"] });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <Apple size={18} strokeWidth={2} className="text-primary" />
        Diet plan builder
      </h1>

      <Card>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="diet-name">Plan name</Label>
            <Input
              id="diet-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-8 w-64"
            />
          </div>

          <div className="space-y-2">
            {items.map((item, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <select
                  value={item.food_item_id}
                  onChange={(e) => updateItem(i, { food_item_id: e.target.value })}
                  className={`${selectClass} flex-1`}
                >
                  {foodItemList.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.name_en}
                    </option>
                  ))}
                </select>
                <Input
                  type="number"
                  value={item.grams}
                  onChange={(e) => updateItem(i, { grams: Number(e.target.value) })}
                  className="h-8 w-20"
                />
                <span className="text-muted-foreground">g</span>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="text-destructive hover:text-destructive"
                  onClick={() => removeItem(i)}
                  aria-label="Remove item"
                >
                  <X size={14} strokeWidth={2} />
                </Button>
              </div>
            ))}
            <Button type="button" size="sm" variant="outline" onClick={addItem}>
              + Food item
            </Button>
          </div>

          <p className="font-dashboard-mono text-sm font-medium">
            Live totals: {totals.kcal} kcal &middot; {totals.protein}g protein
          </p>

          <Button onClick={save} disabled={saving || !name || items.length === 0}>
            {saving ? "..." : "Save plan"}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-muted-foreground">Existing plans</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="divide-y text-sm">
            {planList.map((plan) => (
              <li key={plan.id} className="py-2">
                {plan.name} &middot;{" "}
                <span className="font-dashboard-mono">
                  {plan.kcal_target} kcal &middot; {plan.protein_g}g protein
                </span>
              </li>
            ))}
            {planList.length === 0 && (
              <li className="py-2 text-muted-foreground">No plans yet.</li>
            )}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
