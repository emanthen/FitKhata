"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  completeCall,
  listCallQueue,
  type RetentionCall,
  type RetentionCallOutcome,
} from "@fitkhata/api-client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const OUTCOMES: { value: RetentionCallOutcome; label: string }[] = [
  { value: "reached", label: "Reached" },
  { value: "no_answer", label: "No answer" },
  { value: "coming_back", label: "Coming back" },
  { value: "injured", label: "Injured" },
  { value: "quitting", label: "Quitting" },
  { value: "call_back", label: "Call back later" },
];

function QueueRow({ call }: { call: RetentionCall }) {
  const queryClient = useQueryClient();
  const [callBackOn, setCallBackOn] = useState("");
  const [pendingOutcome, setPendingOutcome] = useState<RetentionCallOutcome | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(outcome: RetentionCallOutcome) {
    if (outcome === "call_back" && !callBackOn) {
      setPendingOutcome(outcome);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await completeCall(call.id, {
        outcome,
        call_back_on: outcome === "call_back" ? callBackOn : undefined,
      });
      queryClient.invalidateQueries({ queryKey: ["retention", "call-queue"] });
    } catch {
      setError("Couldn't record that outcome.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <li className="space-y-2 rounded border p-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-medium">{call.member_name}</p>
          <a href={`tel:${call.member_phone}`} className="text-sm text-blue-600 hover:underline">
            {call.member_phone}
          </a>
        </div>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex flex-wrap gap-1.5">
        {OUTCOMES.map((o) => (
          <Button
            key={o.value}
            type="button"
            variant="outline"
            disabled={submitting}
            onClick={() => submit(o.value)}
            className="h-7 px-2 text-xs"
          >
            {o.label}
          </Button>
        ))}
      </div>
      {pendingOutcome === "call_back" && (
        <div className="flex items-center gap-2">
          <Input
            type="date"
            value={callBackOn}
            onChange={(e) => setCallBackOn(e.target.value)}
            className="h-8 w-40"
          />
          <Button
            type="button"
            disabled={!callBackOn || submitting}
            onClick={() => submit("call_back")}
            className="h-8"
          >
            Confirm call-back date
          </Button>
        </div>
      )}
    </li>
  );
}

export default function CallQueuePage() {
  const query = useQuery({
    queryKey: ["retention", "call-queue"],
    queryFn: () => listCallQueue(),
  });

  return (
    <div className="max-w-xl space-y-4">
      <h1 className="text-2xl font-semibold">Morning call queue</h1>
      <p className="text-sm opacity-60">
        A call stays on this list until you pick an outcome &mdash; there&apos;s no way to
        dismiss it without one.
      </p>

      {query.isLoading && <p className="text-sm opacity-60">Loading...</p>}
      {query.data && query.data.length === 0 && (
        <p className="text-sm opacity-60">Nothing queued for today. Nice work.</p>
      )}

      <ul className="space-y-2">
        {query.data?.map((call) => <QueueRow key={call.id} call={call} />)}
      </ul>
    </div>
  );
}
