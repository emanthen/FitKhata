"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { Menu } from "lucide-react";

import { Logo } from "@/components/logo";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

const LINKS = [
  { href: "/#features", key: "navFeatures" as const, route: false },
  { href: "/#pricing", key: "navPricing" as const, route: false },
  { href: "/about", key: "navAbout" as const, route: true },
  { href: "/contact", key: "navContact" as const, route: true },
];

export function MarketingNav() {
  const t = useTranslations("marketing");
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 md:px-6">
        <Logo size={26} />

        <nav className="hidden items-center gap-6 lg:flex">
          {LINKS.map((link) => {
            const active = link.route && pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`text-sm font-medium transition-colors ${
                  active ? "text-primary" : "text-foreground/70 hover:text-foreground"
                }`}
              >
                {t(link.key)}
              </Link>
            );
          })}
        </nav>

        <div className="hidden items-center gap-2 lg:flex">
          <LocaleSwitcher />
          <ThemeToggle />
          <Button variant="ghost" size="lg" asChild>
            <Link href="/login">{t("navLogin")}</Link>
          </Button>
          <Button size="lg" className="h-10 px-5" asChild>
            <Link href="/onboarding">{t("navCta")}</Link>
          </Button>
        </div>

        <div className="flex items-center gap-1 lg:hidden">
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
                  <Link
                    key={link.href}
                    href={link.href}
                    onClick={() => setOpen(false)}
                    className="rounded-md px-2 py-2.5 text-sm font-medium text-foreground/80 hover:bg-muted"
                  >
                    {t(link.key)}
                  </Link>
                ))}
              </nav>
              <div className="mt-5 flex items-center justify-between border-t border-border pt-5">
                <LocaleSwitcher />
              </div>
              <div className="mt-3 flex flex-col gap-2">
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
