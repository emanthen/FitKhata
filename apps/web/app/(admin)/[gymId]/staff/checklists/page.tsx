"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createShiftChecklist,
  listShiftChecklists,
  submitChecklistCompletion,
  type ShiftChecklist,
} from "@fitkhata/api-client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StaffTabs } from "@/components/staff/staff-tabs";

function toList<T>(data: T[] | { results: T[] } | undefined): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : data.results;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function ChecklistRunner({ checklist }: { checklist: ShiftChecklist }) {
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [submitted, setSubmitted] = useState(false);

  function toggle(item: string) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(item)) next.delete(item);
      else next.add(item);
      return next;
    });
  }

  async function submit() {
    await submitChecklistCompletion({
      checklist: checklist.id,
      date: today(),
      checked_items: [...checked],
    });
    setSubmitted(true);
  }

  return (
    <div className="space-y-2 rounded border p-3">
      <h2 className="text-sm font-medium">{checklist.name}</h2>
      <ul className="space-y-1">
        {checklist.items.map((item) => (
          <li key={item} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={checked.has(item)}
              onChange={() => toggle(item)}
              id={`${checklist.id}-${item}`}
            />
            <label htmlFor={`${checklist.id}-${item}`}>{item}</label>
          </li>
        ))}
      </ul>
      <Button size="sm" onClick={submit} disabled={submitted}>
        {submitted ? "Submitted for today" : "Submit"}
      </Button>
    </div>
  );
}

export default function ChecklistsPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [itemsText, setItemsText] = useState("");

  const query = useQuery({ queryKey: ["staff", "checklists"], queryFn: listShiftChecklists });
  const checklists = toList<ShiftChecklist>(query.data);

  async function createChecklist(e: React.FormEvent) {
    e.preventDefault();
    const items = itemsText
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    await createShiftChecklist({ name, items });
    setName("");
    setItemsText("");
    queryClient.invalidateQueries({ queryKey: ["staff", "checklists"] });
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">Staff</h1>
      <StaffTabs />

      <div className="space-y-3">
        {checklists.map((c) => (
          <ChecklistRunner key={c.id} checklist={c} />
        ))}
        {checklists.length === 0 && (
          <p className="text-sm opacity-60">No checklist templates yet — add one below.</p>
        )}
      </div>

      <form onSubmit={createChecklist} className="space-y-2 rounded border p-3">
        <h2 className="text-sm font-medium">New checklist template</h2>
        <div className="space-y-1">
          <Label htmlFor="checklist-name">Name</Label>
          <Input
            id="checklist-name"
            placeholder="Opening"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="checklist-items">Items (one per line)</Label>
          <textarea
            id="checklist-items"
            value={itemsText}
            onChange={(e) => setItemsText(e.target.value)}
            rows={4}
            className="w-full rounded border bg-background p-2 text-sm"
            required
          />
        </div>
        <Button type="submit">Create</Button>
      </form>
    </div>
  );
}
