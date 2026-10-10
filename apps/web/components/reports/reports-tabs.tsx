"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";

const TABS = [
  { label: "Overview", href: "" },
  { label: "Attendance", href: "/attendance" },
  { label: "Cohorts", href: "/cohorts" },
  { label: "Dues", href: "/dues" },
  { label: "VAT register", href: "/vat-register" },
];

/** Shared tab row for every /reports/* sub-page — mirrors staff-tabs.tsx. */
export function ReportsTabs() {
  const { gymId } = useParams<{ gymId: string }>();
  const pathname = usePathname();
  const base = `/${gymId}/reports`;

  return (
    <nav className="flex gap-1 border-b pb-2 text-sm">
      {TABS.map((tab) => {
        const href = `${base}${tab.href}`;
        const active = pathname === href;
        return (
          <Link
            key={tab.href}
            href={href}
            className={`rounded px-2.5 py-1 ${
              active
                ? "bg-neutral-100 font-medium dark:bg-neutral-800"
                : "opacity-70 hover:opacity-100"
            }`}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
