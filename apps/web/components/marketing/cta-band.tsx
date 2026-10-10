import Link from "next/link";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";

export function MarketingCtaBand() {
  const t = useTranslations("marketing");

  return (
    <section className="bg-primary">
      <div className="mx-auto flex max-w-7xl flex-col items-start gap-6 px-4 py-16 md:flex-row md:items-center md:justify-between md:px-6 md:py-20">
        <div>
          <h2 className="max-w-[20ch] text-3xl font-bold tracking-tight text-primary-foreground md:text-4xl">
            {t("ctaHeading")}
          </h2>
          <p className="mt-2 text-primary-foreground/85">{t("ctaBody")}</p>
        </div>
        <Button
          size="lg"
          className="h-11 shrink-0 bg-primary-foreground px-6 text-base text-primary hover:bg-primary-foreground/90"
          asChild
        >
          <Link href="/onboarding">{t("ctaButton")}</Link>
        </Button>
      </div>
    </section>
  );
}
