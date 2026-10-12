"use client";

import { useTranslations } from "next-intl";
import { Plus } from "lucide-react";

const ITEMS = [
  { qKey: "faq1Q", aKey: "faq1A" },
  { qKey: "faq2Q", aKey: "faq2A" },
  { qKey: "faq3Q", aKey: "faq3A" },
  { qKey: "faq4Q", aKey: "faq4A" },
  { qKey: "faq5Q", aKey: "faq5A" },
  { qKey: "faq6Q", aKey: "faq6A" },
] as const;

export function MarketingFaq() {
  const t = useTranslations("marketing");

  return (
    <section className="mx-auto max-w-3xl px-4 py-16 md:px-6 md:py-24">
      <h2 className="font-marketing-display text-center text-4xl font-bold tracking-tight md:text-5xl">
        {t("faqHeading")}
      </h2>

      <div className="mt-10 divide-y rounded-2xl border">
        {ITEMS.map((item) => (
          <details key={item.qKey} className="group p-5">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-left text-sm font-medium marker:content-none">
              {t(item.qKey)}
              <Plus
                size={16}
                strokeWidth={2}
                className="shrink-0 text-muted-foreground transition-transform group-open:rotate-45"
              />
            </summary>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{t(item.aKey)}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
