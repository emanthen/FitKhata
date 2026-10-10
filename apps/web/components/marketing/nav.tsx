"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Menu } from "lucide-react";

import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

const LINKS = [
  { href: "#features", key: "navFeatures" as const },
  { href: "#pricing", key: "navPricing" as const },
];

export function MarketingNav() {
  const t = useTranslations("marketing");
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 md:px-6">
        <Logo size={26} />

        <nav className="hidden items-center gap-7 md:flex">
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-foreground/70 transition-colors hover:text-foreground"
            >
              {t(link.key)}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          <ThemeToggle />
          <Button variant="ghost" size="lg" asChild>
            <Link href="/login">{t("navLogin")}</Link>
          </Button>
          <Button size="lg" className="h-10 px-5" asChild>
            <Link href="/onboarding">{t("navCta")}</Link>
          </Button>
        </div>

        <div className="flex items-center gap-1 md:hidden">
          <ThemeToggle />
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Open menu">
                <Menu size={20} />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-72 p-5">
              <SheetTitle asChild>
                <div className="mb-6">
                  <Logo size={24} />
                </div>
              </SheetTitle>
              <nav className="flex flex-col gap-1">
                {LINKS.map((link) => (
                  <a
                    key={link.href}
                    href={link.href}
                    onClick={() => setOpen(false)}
                    className="rounded-md px-2 py-2.5 text-sm font-medium text-foreground/80 hover:bg-muted"
                  >
                    {t(link.key)}
                  </a>
                ))}
              </nav>
              <div className="mt-5 flex flex-col gap-2 border-t border-border pt-5">
                <Button variant="outline" asChild>
                  <Link href="/login">{t("navLogin")}</Link>
                </Button>
                <Button asChild>
                  <Link href="/onboarding">{t("navCta")}</Link>
                </Button>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}
