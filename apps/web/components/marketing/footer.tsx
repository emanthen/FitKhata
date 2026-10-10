import { useTranslations } from "next-intl";

import { Logo } from "@/components/logo";

export function MarketingFooter() {
  const t = useTranslations("marketing");
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-7xl flex-col gap-8 px-4 py-12 md:flex-row md:items-start md:justify-between md:px-6">
        <div>
          <Logo size={24} />
          <p className="mt-3 max-w-[32ch] text-sm text-muted-foreground">{t("footerTagline")}</p>
        </div>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("footerProduct")}
          </p>
          <nav className="mt-3 flex flex-col gap-2">
            <a href="#features" className="text-sm text-foreground/75 hover:text-foreground">
              {t("navFeatures")}
            </a>
            <a href="#pricing" className="text-sm text-foreground/75 hover:text-foreground">
              {t("navPricing")}
            </a>
            <a href="/login" className="text-sm text-foreground/75 hover:text-foreground">
              {t("navLogin")}
            </a>
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
