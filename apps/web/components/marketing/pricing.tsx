"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { motion, useReducedMotion } from "motion/react";
import { Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

// Rs figures sourced from apps/api/saas/migrations/0002_seed_plans.py — the
// real seeded SRS §12.1 pricing, not placeholder numbers.
const PLANS = [
  {
    nameKey: "plan1Name",
    monthlyNpr: 999,
    setupNpr: 3000,
    memberLimit: 150,
    featureKeys: ["plan1Feature1", "plan1Feature2", "plan1Feature3"],
    highlight: false,
  },
  {
    nameKey: "plan2Name",
    monthlyNpr: 1999,
    setupNpr: 5000,
    memberLimit: 1000,
    featureKeys: ["plan2Feature1", "plan2Feature2", "plan2Feature3"],
    highlight: true,
  },
  {
    nameKey: "plan3Name",
    monthlyNpr: 4999,
    setupNpr: 15000,
    memberLimit: null,
    featureKeys: ["plan3Feature1", "plan3Feature2", "plan3Feature3"],
    highlight: false,
  },
] as const;

const formatNpr = (n: number) => new Intl.NumberFormat("en-IN").format(n);

export function MarketingPricing() {
  const t = useTranslations("marketing");
  const reduce = useReducedMotion();

  return (
    <section id="pricing" className="mx-auto max-w-7xl px-4 py-16 md:px-6 md:py-24">
      <div className="flex flex-col items-start gap-2 md:flex-row md:items-end md:justify-between">
        <h2 className="font-marketing-display text-4xl font-bold tracking-tight md:text-5xl">
          {t("pricingHeading")}
        </h2>
        <p className="text-sm text-muted-foreground">{t("pricingNote")}</p>
      </div>

      <div className="mt-10 grid grid-cols-1 gap-5 md:grid-cols-3">
        {PLANS.map((plan, i) => (
          <motion.div
            key={plan.nameKey}
            initial={reduce ? false : { opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.45, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
            className={`flex flex-col rounded-2xl border p-7 ${
              plan.highlight
                ? "border-primary bg-primary/5 shadow-lg shadow-primary/10"
                : "border-border"
            }`}
          >
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">{t(plan.nameKey)}</h3>
              {plan.highlight && <Badge>{t("pricingMostPopular")}</Badge>}
            </div>

            <div className="mt-4 flex items-baseline gap-1">
              <span className="font-marketing-display text-4xl font-bold tracking-tight">
                Rs {formatNpr(plan.monthlyNpr)}
              </span>
              <span className="text-sm text-muted-foreground">{t("pricingPerMonth")}</span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {t("pricingSetupFee", { amount: formatNpr(plan.setupNpr) })}
            </p>

            <ul className="mt-6 flex flex-col gap-2.5">
              <li className="flex items-start gap-2.5 text-sm">
                <Check size={16} strokeWidth={2.5} className="mt-0.5 shrink-0 text-accent" />
                <span>
                  {plan.memberLimit === null
                    ? t("pricingMemberUnlimited")
                    : t("pricingMemberLimit", { count: plan.memberLimit })}
                </span>
              </li>
              {plan.featureKeys.map((key) => (
                <li key={key} className="flex items-start gap-2.5 text-sm">
                  <Check size={16} strokeWidth={2.5} className="mt-0.5 shrink-0 text-accent" />
                  <span>{t(key)}</span>
                </li>
              ))}
            </ul>

            <Button
              className="mt-7 h-10"
              variant={plan.highlight ? "default" : "outline"}
              asChild
            >
              <Link href="/onboarding">{t("pricingCta")}</Link>
            </Button>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
