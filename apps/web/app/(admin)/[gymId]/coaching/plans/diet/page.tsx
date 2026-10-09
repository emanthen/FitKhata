"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createDietPlan,
  listDietPlans,
  listFoodItems,
  type DietPlanMealItem,
} from "@fitkhata/api-client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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
      <h1 className="text-2xl font-semibold">Diet plan builder</h1>

      <div className="space-y-3 rounded border p-4">
        <div className="space-y-1">
          <Label htmlFor="diet-name">Plan name</Label>
          <Input id="diet-name" value={name} onChange={(e) => setName(e.target.value)} className="w-64" />
        </div>

        <div className="space-y-2">
          {items.map((item, i) => (
            <div key={i} className="flex items-center gap-2 text-sm">
              <select
                value={item.food_item_id}
                onChange={(e) => updateItem(i, { food_item_id: e.target.value })}
                className="h-8 flex-1 rounded border px-2"
              >
                {foodItemList.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name_en}
                  </option>
                ))}
              </select>
              <input
                type="number"
                value={item.grams}
                onChange={(e) => updateItem(i, { grams: Number(e.target.value) })}
                className="h-8 w-20 rounded border px-2"
              />
              <span className="opacity-60">g</span>
              <button onClick={() => removeItem(i)} className="text-xs text-red-600 hover:underline">
                Remove
              </button>
            </div>
          ))}
          <Button type="button" size="sm" variant="outline" onClick={addItem}>
            + Food item
          </Button>
        </div>

        <p className="text-sm font-medium">
          Live totals: {totals.kcal} kcal &middot; {totals.protein}g protein
        </p>

        <Button onClick={save} disabled={saving || !name || items.length === 0}>
          {saving ? "..." : "Save plan"}
        </Button>
      </div>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">Existing plans</h2>
        <ul className="space-y-1 text-sm">
          {planList.map((plan) => (
            <li key={plan.id} className="rounded border px-3 py-2">
              {plan.name} &middot; {plan.kcal_target} kcal &middot; {plan.protein_g}g protein
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
