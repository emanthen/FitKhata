"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { motion, useReducedMotion } from "motion/react";
import { ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";

export function MarketingCtaBand() {
  const t = useTranslations("marketing");
  const reduce = useReducedMotion();

  return (
    <section className="relative overflow-hidden bg-primary">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.15]"
        style={{
          backgroundImage: "radial-gradient(currentColor 1.5px, transparent 1.5px)",
          backgroundSize: "20px 20px",
          color: "var(--primary-foreground)",
        }}
      />

      <motion.div
        initial={reduce ? false : { opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.5 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="relative mx-auto flex max-w-7xl flex-col items-start gap-6 px-4 py-16 md:flex-row md:items-center md:justify-between md:px-6 md:py-20"
      >
        <div>
          <h2 className="max-w-[20ch] text-3xl font-bold tracking-tight text-primary-foreground md:text-4xl">
            {t("ctaHeading")}
          </h2>
          <p className="mt-2 text-primary-foreground/85">{t("ctaBody")}</p>
        </div>
        <div className="flex shrink-0 flex-col items-start gap-2 md:items-end">
          <Button
            size="lg"
            className="h-11 gap-1.5 bg-primary-foreground px-6 text-base text-primary hover:bg-primary-foreground/90"
            asChild
          >
            <Link href="/onboarding">
              {t("ctaButton")}
              <ArrowRight size={16} strokeWidth={2} />
            </Link>
          </Button>
          <p className="text-xs text-primary-foreground/70">{t("ctaTrust")}</p>
        </div>
      </motion.div>
    </section>
  );
}
