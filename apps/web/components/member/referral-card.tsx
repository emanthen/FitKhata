"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Gift, Share2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

// Mirrors members.services.REFERRAL_REWARD_DAYS — FR-8.8's reward is
// granted server-side on the referred friend's first completed payment
// (members.services.reward_referral); this is purely display copy, no
// endpoint exposes the constant itself.
const REFERRAL_REWARD_DAYS = 7;

/** FR-8.8: member_code doubles as the referral code (see
 * members/models.py's Member.referred_by comment) — this just gives it a
 * shareable frame instead of leaving it as an unlabeled code on the page.
 */
export function ReferralCard({ code }: { code: string }) {
  const t = useTranslations("member");
  const [copied, setCopied] = useState(false);
  const canShare = typeof navigator !== "undefined" && Boolean(navigator.share);

  async function share() {
    const text = t("referralBody", { days: REFERRAL_REWARD_DAYS });
    if (typeof navigator !== "undefined" && navigator.share) {
      try {
        await navigator.share({ title: t("referralTitle"), text: `${text} ${code}` });
        return;
      } catch {
        // user cancelled the share sheet — fall through to copy
      }
    }
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard unavailable — the code is already visible on screen
    }
  }

  return (
    <Card className="w-full">
      <CardContent className="flex flex-col items-center gap-1 text-center">
        <p className="flex items-center gap-1.5 text-sm font-medium">
          <Gift size={14} strokeWidth={2} className="text-accent" />
          {t("referralTitle")}
        </p>
        <p className="font-dashboard-mono text-lg font-semibold tracking-wide">{code}</p>
        <p className="text-sm text-muted-foreground">{t("referralBody", { days: REFERRAL_REWARD_DAYS })}</p>
        <Button variant="ghost" size="sm" onClick={share} className="mt-1 text-primary hover:text-primary">
          <Share2 size={13} strokeWidth={2} data-icon="inline-start" />
          {copied ? t("referralCopied") : canShare ? t("referralShare") : t("referralCopy")}
        </Button>
      </CardContent>
    </Card>
  );
}
