"use client";

import Image from "next/image";
import { useTranslations } from "next-intl";
import { motion, useReducedMotion } from "motion/react";
import { BarChart3, Building2, CreditCard, IdCard, PhoneCall, QrCode } from "lucide-react";

import billingImage from "@/public/images/marketing/feature-billing.jpg";

const ITEMS = [
  { icon: QrCode, titleKey: "feature1Title", bodyKey: "feature1Body", variant: "plain" },
  { icon: CreditCard, titleKey: "feature2Title", bodyKey: "feature2Body", variant: "photo" },
  { icon: IdCard, titleKey: "feature3Title", bodyKey: "feature3Body", variant: "plain" },
  { icon: PhoneCall, titleKey: "feature4Title", bodyKey: "feature4Body", variant: "tint" },
  { icon: BarChart3, titleKey: "feature5Title", bodyKey: "feature5Body", variant: "plain" },
  { icon: Building2, titleKey: "feature6Title", bodyKey: "feature6Body", variant: "gradient" },
] as const;

export function MarketingFeatures() {
  const t = useTranslations("marketing");
  const reduce = useReducedMotion();

  return (
    <section id="features" className="mx-auto max-w-7xl px-4 py-16 md:px-6 md:py-24">
      <h2 className="font-marketing-display max-w-[24ch] text-4xl font-bold tracking-tight md:text-5xl">
        {t("featuresHeading")}
      </h2>

      <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {ITEMS.map((item, i) => {
          const Icon = item.icon;
          const isPhoto = item.variant === "photo";
          const isGradient = item.variant === "gradient";
          const isTint = item.variant === "tint";
          const isDark = isPhoto || isGradient;

          return (
            <motion.div
              key={item.titleKey}
              initial={reduce ? false : { opacity: 0, y: 20, scale: 0.97 }}
              whileInView={{ opacity: 1, y: 0, scale: 1 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ duration: 0.45, delay: i * 0.05, ease: [0.16, 1, 0.3, 1] }}
              className={`relative overflow-hidden rounded-2xl border border-border p-6 ${
                isPhoto ? "sm:col-span-2" : ""
              } ${isTint ? "bg-accent/10" : ""} ${
                isGradient ? "bg-gradient-to-br from-primary to-primary/70" : ""
              } ${!isDark && !isTint ? "bg-card" : ""}`}
            >
              {isPhoto && (
                <>
                  <Image
                    src={billingImage}
                    alt=""
                    fill
                    sizes="(min-width: 1024px) 66vw, 100vw"
                    className="object-cover"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent" />
                </>
              )}
              <div className={`relative ${isDark ? "text-white" : "text-foreground"}`}>
                <span
                  className={`flex size-9 items-center justify-center rounded-full ${
                    isDark ? "bg-white/15" : "bg-primary/10"
                  }`}
                >
                  <Icon size={18} strokeWidth={2} className={isDark ? "text-white" : "text-primary"} />
                </span>
                <h3 className="mt-4 text-lg font-semibold">{t(item.titleKey)}</h3>
                <p
                  className={`mt-1.5 max-w-[38ch] text-sm leading-relaxed ${
                    isDark ? "text-white/85" : "text-muted-foreground"
                  }`}
                >
                  {t(item.bodyKey)}
                </p>
              </div>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
