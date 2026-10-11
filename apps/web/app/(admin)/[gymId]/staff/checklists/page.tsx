"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createShiftChecklist,
  listShiftChecklists,
  submitChecklistCompletion,
  type ShiftChecklist,
} from "@fitkhata/api-client";
import { CircleCheck, IdCard, ListChecks } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
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
    <Card>
      <CardContent className="space-y-2.5">
        <h2 className="text-sm font-medium">{checklist.name}</h2>
        <ul className="space-y-1.5">
          {checklist.items.map((item) => (
            <li key={item} className="flex items-center gap-2 text-sm">
              <Checkbox
                id={`${checklist.id}-${item}`}
                checked={checked.has(item)}
                onCheckedChange={() => toggle(item)}
              />
              <label htmlFor={`${checklist.id}-${item}`}>{item}</label>
            </li>
          ))}
        </ul>
        <Button size="sm" onClick={submit} disabled={submitted}>
          {submitted && <CircleCheck size={13} strokeWidth={2} data-icon="inline-start" />}
          {submitted ? "Submitted for today" : "Submit"}
        </Button>
      </CardContent>
    </Card>
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
      <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
        <IdCard size={18} strokeWidth={2} className="text-primary" />
        Staff
      </h1>
      <StaffTabs />

      <div className="space-y-3">
        {checklists.map((c) => (
          <ChecklistRunner key={c.id} checklist={c} />
        ))}
        {checklists.length === 0 && (
          <p className="text-sm text-muted-foreground">No checklist templates yet - add one below.</p>
        )}
      </div>

      <Card>
        <CardContent>
          <form onSubmit={createChecklist} className="space-y-3">
            <h2 className="flex items-center gap-1.5 text-sm font-medium">
              <ListChecks size={15} strokeWidth={2} className="text-primary" />
              New checklist template
            </h2>
            <div className="space-y-1.5">
              <Label htmlFor="checklist-name">Name</Label>
              <Input
                id="checklist-name"
                placeholder="Opening"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="h-8"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="checklist-items">Items (one per line)</Label>
              <textarea
                id="checklist-items"
                value={itemsText}
                onChange={(e) => setItemsText(e.target.value)}
                rows={4}
                className="w-full rounded-lg border border-input bg-transparent p-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                required
              />
            </div>
            <Button type="submit" size="sm">
              Create
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
