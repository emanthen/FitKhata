import { useTranslations } from "next-intl";
import { Banknote, WifiOff, Wallet } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { MarketingCtaBand } from "@/components/marketing/cta-band";

const PRINCIPLES = [
  { icon: Wallet, titleKey: "aboutPrinciple1Title", bodyKey: "aboutPrinciple1Body" },
  { icon: Banknote, titleKey: "aboutPrinciple2Title", bodyKey: "aboutPrinciple2Body" },
  { icon: WifiOff, titleKey: "aboutPrinciple3Title", bodyKey: "aboutPrinciple3Body" },
] as const;

export default function AboutPage() {
  const t = useTranslations("marketing");

  return (
    <>
      <section className="mx-auto max-w-3xl px-4 pt-14 pb-16 text-center md:px-6 md:pt-20">
        <h1 className="text-4xl font-bold leading-[1.1] tracking-tight md:text-5xl">
          {t("aboutHeading")}
        </h1>
        <p className="mx-auto mt-5 max-w-[60ch] text-base leading-relaxed text-muted-foreground md:text-lg">
          {t("aboutBody")}
        </p>
      </section>

      <section className="mx-auto max-w-5xl px-4 pb-20 md:px-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {PRINCIPLES.map((p) => {
            const Icon = p.icon;
            return (
              <Card key={p.titleKey}>
                <CardContent>
                  <Icon size={22} strokeWidth={1.75} className="text-primary" />
                  <h2 className="mt-4 text-lg font-semibold">{t(p.titleKey)}</h2>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                    {t(p.bodyKey)}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      <MarketingCtaBand />
    </>
  );
}
