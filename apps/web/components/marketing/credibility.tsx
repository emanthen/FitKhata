"use client";

import Image from "next/image";
import { useTranslations } from "next-intl";
import { motion, useReducedMotion } from "motion/react";
import { Check } from "lucide-react";

import coachImage from "@/public/images/marketing/usecase-coaching.jpg";

const ITEM_KEYS = ["credibility1", "credibility2", "credibility3", "credibility4"] as const;

export function MarketingCredibility() {
  const t = useTranslations("marketing");
  const reduce = useReducedMotion();

  return (
    <section className="bg-muted/40">
      <div className="mx-auto grid max-w-7xl items-center gap-10 px-4 py-16 md:grid-cols-2 md:gap-14 md:px-6 md:py-24">
        <motion.div
          initial={reduce ? false : { opacity: 0, scale: 0.96 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="relative order-2 aspect-[3/4] overflow-hidden rounded-2xl shadow-[0_30px_70px_-30px_rgb(0_0_0_/_0.35)] md:order-1"
        >
          <Image
            src={coachImage}
            alt=""
            fill
            sizes="(min-width: 768px) 45vw, 90vw"
            className="object-cover"
          />
        </motion.div>

        <motion.div
          initial={reduce ? false : { opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="order-1 md:order-2"
        >
          <h2 className="font-marketing-display max-w-[22ch] text-4xl font-bold tracking-tight md:text-5xl">
            {t("credibilityHeading")}
          </h2>
          <ul className="mt-7 flex flex-col gap-4">
            {ITEM_KEYS.map((key) => (
              <li key={key} className="flex items-start gap-3">
                <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-accent/15 text-accent">
                  <Check size={13} strokeWidth={2.5} />
                </span>
                <span className="text-sm leading-relaxed text-foreground/85 md:text-base">
                  {t(key)}
                </span>
              </li>
            ))}
          </ul>
        </motion.div>
      </div>
    </section>
  );
}
