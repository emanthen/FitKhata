"use client";

import { useTranslations } from "next-intl";
import { motion, useReducedMotion } from "motion/react";

const STEPS = [
  { titleKey: "how1Title", bodyKey: "how1Body" },
  { titleKey: "how2Title", bodyKey: "how2Body" },
  { titleKey: "how3Title", bodyKey: "how3Body" },
  { titleKey: "how4Title", bodyKey: "how4Body" },
] as const;

export function MarketingHowItWorks() {
  const t = useTranslations("marketing");
  const reduce = useReducedMotion();

  return (
    <section className="mx-auto max-w-7xl px-4 py-16 md:px-6 md:py-24">
      <h2 className="mx-auto max-w-xl text-center text-3xl font-bold tracking-tight md:text-4xl">
        {t("howHeading")}
      </h2>

      <div className="mt-12 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((step, i) => (
          <motion.div
            key={step.titleKey}
            initial={reduce ? false : { opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.4 }}
            transition={{ duration: 0.45, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
          >
            <span className="font-dashboard-mono flex size-9 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
              {i + 1}
            </span>
            <h3 className="mt-4 text-lg font-semibold">{t(step.titleKey)}</h3>
            <p className="mt-1.5 max-w-[32ch] text-sm leading-relaxed text-muted-foreground">
              {t(step.bodyKey)}
            </p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
