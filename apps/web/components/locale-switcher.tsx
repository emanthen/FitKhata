"use client";

import { useLocale } from "next-intl";
import { useRouter } from "next/navigation";

const LOCALES = [
  { code: "ne", label: "ने" },
  { code: "en", label: "EN" },
] as const;

export function LocaleSwitcher({ className = "" }: { className?: string }) {
  const locale = useLocale();
  const router = useRouter();

  function switchTo(code: string) {
    if (code === locale) return;
    document.cookie = `locale=${code}; path=/; max-age=31536000`;
    router.refresh();
  }

  return (
    <div className={`inline-flex items-center gap-0.5 rounded-full border p-0.5 text-xs ${className}`}>
      {LOCALES.map((l) => (
        <button
          key={l.code}
          onClick={() => switchTo(l.code)}
          aria-current={locale === l.code}
          className={`rounded-full px-2 py-1 font-medium transition-colors ${
            locale === l.code
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}
