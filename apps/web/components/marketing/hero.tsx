"use client";

import Link from "next/link";
import Image from "next/image";
import { useTranslations } from "next-intl";
import { motion, useReducedMotion } from "motion/react";
import { QrCode } from "lucide-react";

import { Button } from "@/components/ui/button";
import heroImage from "@/public/images/marketing/hero-checkin.jpg";

// Corner brackets echo the logo's QR scan-frame mark so the hero carries the
// brand signature instead of a generic bordered photo.
function ScanCorners() {
  const corner = "M2 8V2H8" as const;
  return (
    <>
      <svg className="absolute left-3 top-3 size-6 text-background/90" viewBox="0 0 10 10" fill="none">
        <path d={corner} stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      <svg className="absolute right-3 top-3 size-6 rotate-90 text-background/90" viewBox="0 0 10 10" fill="none">
        <path d={corner} stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      <svg className="absolute bottom-3 left-3 size-6 -rotate-90 text-background/90" viewBox="0 0 10 10" fill="none">
        <path d={corner} stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      <svg className="absolute bottom-3 right-3 size-6 rotate-180 text-background/90" viewBox="0 0 10 10" fill="none">
        <path d={corner} stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    </>
  );
}

export function MarketingHero() {
  const t = useTranslations("marketing");
  const reduce = useReducedMotion();

  return (
    <section className="mx-auto grid max-w-7xl items-center gap-10 px-4 pt-14 pb-16 md:grid-cols-[1.05fr_0.95fr] md:gap-12 md:px-6 md:pt-20">
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <h1 className="font-marketing-display max-w-[16ch] text-5xl font-bold leading-[0.98] tracking-tight text-balance md:text-6xl lg:text-7xl">
          {t("heroTitle")}
        </h1>
        <p className="mt-5 max-w-[46ch] text-base leading-relaxed text-muted-foreground md:text-lg">
          {t("heroSubtitle")}
        </p>
        <div className="mt-8 flex flex-wrap items-center gap-3">
          <Button size="lg" className="h-11 px-6 text-base" asChild>
            <Link href="/onboarding">{t("heroCtaPrimary")}</Link>
          </Button>
          <Button variant="outline" size="lg" className="h-11 px-6 text-base" asChild>
            <a href="#pricing">{t("heroCtaSecondary")}</a>
          </Button>
        </div>
      </motion.div>

      <motion.div
        initial={reduce ? false : { opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
        className="relative"
      >
        <div className="relative aspect-[4/5] overflow-hidden rounded-2xl shadow-[0_30px_70px_-30px_rgb(0_0_0_/_0.35)]">
          <Image
            src={heroImage}
            alt=""
            fill
            priority
            sizes="(min-width: 768px) 45vw, 90vw"
            className="object-cover"
          />
          <ScanCorners />
        </div>

        {/* Illustrative figure, matches the organic-number style used in the
            product-preview panel below — not wired to live data. */}
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.35, ease: [0.16, 1, 0.3, 1] }}
          className="absolute -bottom-5 left-5 flex items-center gap-3 rounded-xl bg-card px-4 py-3 shadow-xl"
        >
          <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
            <QrCode size={18} strokeWidth={2} />
          </span>
          <div>
            <p className="font-dashboard-mono text-lg font-semibold leading-none tabular-nums">128</p>
            <p className="text-xs leading-none text-muted-foreground">{t("heroStatLabel")}</p>
          </div>
        </motion.div>
      </motion.div>
    </section>
  );
}
