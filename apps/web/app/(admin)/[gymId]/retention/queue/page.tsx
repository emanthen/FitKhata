"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  completeCall,
  listCallQueue,
  type RetentionCall,
  type RetentionCallOutcome,
} from "@fitkhata/api-client";
import { Phone, PhoneCall, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

const OUTCOME_KEYS: Record<RetentionCallOutcome, string> = {
  reached: "retentionOutcomeReached",
  no_answer: "retentionOutcomeNoAnswer",
  coming_back: "retentionOutcomeComingBack",
  injured: "retentionOutcomeInjured",
  quitting: "retentionOutcomeQuitting",
  call_back: "retentionOutcomeCallBack",
};
const OUTCOMES: RetentionCallOutcome[] = [
  "reached",
  "no_answer",
  "coming_back",
  "injured",
  "quitting",
  "call_back",
];

function QueueRow({ call }: { call: RetentionCall }) {
  const t = useTranslations("admin");
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
      setError(t("retentionOutcomeError"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardContent className="space-y-2.5">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium">{call.member_name}</p>
            <a
              href={`tel:${call.member_phone}`}
              className="font-dashboard-mono flex items-center gap-1.5 text-sm text-primary hover:underline"
            >
              <Phone size={12} strokeWidth={2} />
              {call.member_phone}
            </a>
          </div>
        </div>
        {error && (
          <p className="flex items-center gap-1.5 text-sm text-destructive">
            <TriangleAlert size={13} strokeWidth={2} />
            {error}
          </p>
        )}
        <div className="flex flex-wrap gap-1.5">
          {OUTCOMES.map((o) => (
            <Button
              key={o}
              type="button"
              variant="outline"
              disabled={submitting}
              onClick={() => submit(o)}
              className="h-7 px-2 text-xs"
            >
              {t(OUTCOME_KEYS[o])}
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
              size="sm"
              disabled={!callBackOn || submitting}
              onClick={() => submit("call_back")}
            >
              {t("retentionConfirmCallBackDate")}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function CallQueuePage() {
  const t = useTranslations("admin");
  const query = useQuery({
    queryKey: ["retention", "call-queue"],
    queryFn: () => listCallQueue(),
  });

  return (
    <div className="max-w-xl space-y-4">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <PhoneCall size={18} strokeWidth={2} className="text-primary" />
          {t("retentionQueueTitle")}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("retentionQueueDescription")}</p>
      </div>

      {query.isLoading && (
        <div className="space-y-2">
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-24 w-full rounded-xl" />
        </div>
      )}
      {query.data && query.data.length === 0 && (
        <p className="text-sm text-muted-foreground">{t("retentionQueueEmpty")}</p>
      )}

      <ul className="space-y-2">
        {query.data?.map((call) => <QueueRow key={call.id} call={call} />)}
      </ul>
    </div>
  );
}
