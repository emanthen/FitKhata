"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useTranslations } from "next-intl";

/** Shared tab row for every /reports/* sub-page — mirrors staff-tabs.tsx. */
export function ReportsTabs() {
  const { gymId } = useParams<{ gymId: string }>();
  const pathname = usePathname();
  const t = useTranslations("admin");
  const base = `/${gymId}/reports`;

  const TABS = [
    { label: t("reportsTabOverview"), href: "" },
    { label: t("reportsTabAttendance"), href: "/attendance" },
    { label: t("reportsTabCohorts"), href: "/cohorts" },
    { label: t("reportsTabDues"), href: "/dues" },
    { label: t("reportsTabVatRegister"), href: "/vat-register" },
    { label: t("reportsTabAccountingExport"), href: "/accounting-export" },
  ];

  return (
    <nav className="flex gap-1 border-b pb-2 text-sm">
      {TABS.map((tab) => {
        const href = `${base}${tab.href}`;
        const active = pathname === href;
        return (
          <Link
            key={tab.href}
            href={href}
            className={`rounded-md px-2.5 py-1 transition-colors ${
              active
                ? "bg-primary/10 font-medium text-primary"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
