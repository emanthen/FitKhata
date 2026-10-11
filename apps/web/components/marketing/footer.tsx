import Link from "next/link";
import { useTranslations } from "next-intl";

import { Logo } from "@/components/logo";
import { LocaleSwitcher } from "@/components/locale-switcher";

export function MarketingFooter() {
  const t = useTranslations("marketing");
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-border">
      <div className="mx-auto grid max-w-7xl grid-cols-2 gap-8 px-4 py-12 md:grid-cols-4 md:px-6">
        <div className="col-span-2 md:col-span-1">
          <Logo size={24} />
          <p className="mt-3 max-w-[32ch] text-sm text-muted-foreground">{t("footerTagline")}</p>
          <LocaleSwitcher className="mt-4" />
        </div>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("footerProduct")}
          </p>
          <nav className="mt-3 flex flex-col gap-2">
            <Link href="/#features" className="text-sm text-foreground/75 hover:text-foreground">
              {t("navFeatures")}
            </Link>
            <Link href="/#pricing" className="text-sm text-foreground/75 hover:text-foreground">
              {t("navPricing")}
            </Link>
          </nav>
        </div>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("footerCompany")}
          </p>
          <nav className="mt-3 flex flex-col gap-2">
            <Link href="/about" className="text-sm text-foreground/75 hover:text-foreground">
              {t("navAbout")}
            </Link>
            <Link href="/contact" className="text-sm text-foreground/75 hover:text-foreground">
              {t("navContact")}
            </Link>
          </nav>
        </div>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("footerAccount")}
          </p>
          <nav className="mt-3 flex flex-col gap-2">
            <Link href="/login" className="text-sm text-foreground/75 hover:text-foreground">
              {t("navLogin")}
            </Link>
            <Link href="/onboarding" className="text-sm text-foreground/75 hover:text-foreground">
              {t("navCta")}
            </Link>
          </nav>
        </div>
      </div>
      <div className="border-t border-border px-4 py-5 md:px-6">
        <p className="mx-auto max-w-7xl text-xs text-muted-foreground">
          {t("footerCopyright", { year })}
        </p>
      </div>
    </footer>
  );
}
