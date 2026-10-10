import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import { ThemeProvider } from "@/components/providers/theme-provider";
import { QueryProvider } from "@/components/providers/query-provider";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";
import {
  Barlow,
  Barlow_Condensed,
  Fira_Code,
  Fira_Sans,
  Geist,
  Noto_Sans_Devanagari,
  Outfit,
} from "next/font/google";
import { cn } from "@/lib/utils";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });
// next/font/google self-hosts this at build time exactly like Geist above
// (no runtime Google Fonts request) — the only gap Geist leaves is
// Devanagari glyph coverage, which this covers for every `ne`-locale page,
// not just the Member PWA.
const devanagari = Noto_Sans_Devanagari({
  subsets: ["devanagari"],
  variable: "--font-devanagari",
});

// Per-surface type families (see the Phase 0 moodboard) — loaded once here,
// applied via a font-* utility class scoped to each route group's own
// layout so they don't fight the ne/en Geist/Devanagari switch above.
const firaSans = Fira_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-dashboard",
});
const firaCode = Fira_Code({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-dashboard-mono",
});
const barlowCondensed = Barlow_Condensed({
  subsets: ["latin"],
  weight: ["500", "600", "700", "800"],
  variable: "--font-marketing-display",
});
const barlow = Barlow({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-marketing",
});
// Deliberately not Inter — see Phase 0 moodboard's notes on why a generic
// default was rejected here too.
const outfit = Outfit({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-pwa",
});

export const metadata: Metadata = {
  title: "FitKhata",
  description: "Multi-tenant gym management for Nepal",
  manifest: "/manifest.json",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html
      lang={locale}
      suppressHydrationWarning
      className={cn(
        locale === "ne" ? "font-devanagari" : "font-sans",
        geist.variable,
        devanagari.variable,
        firaSans.variable,
        firaCode.variable,
        barlowCondensed.variable,
        barlow.variable,
        outfit.variable
      )}
    >
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          <NextIntlClientProvider locale={locale} messages={messages}>
            <QueryProvider>
              <TooltipProvider delayDuration={200}>
                {children}
                <Toaster />
              </TooltipProvider>
            </QueryProvider>
          </NextIntlClientProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
