"use client";

import Link from "next/link";
import Image from "next/image";
import { useTranslations } from "next-intl";
import { motion, useReducedMotion } from "motion/react";

import { Button } from "@/components/ui/button";
import heroImage from "@/public/images/marketing/hero-checkin.jpg";

export function MarketingHero() {
  const t = useTranslations("marketing");
  const reduce = useReducedMotion();

  return (
    <section className="mx-auto grid max-w-7xl items-center gap-10 px-4 pt-14 pb-16 md:grid-cols-2 md:gap-12 md:px-6 md:pt-20">
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <h1 className="text-4xl font-bold leading-[1.05] tracking-tight text-balance md:text-5xl lg:text-6xl">
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
        className="relative aspect-square overflow-hidden rounded-2xl border border-border"
      >
        <Image
          src={heroImage}
          alt=""
          fill
          priority
          sizes="(min-width: 768px) 45vw, 90vw"
          className="object-cover"
        />
      </motion.div>
    </section>
  );
}
