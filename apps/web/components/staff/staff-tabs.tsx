"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";

const TABS = [
  { label: "Roles", href: "" },
  { label: "Payroll", href: "/payroll" },
  { label: "Roster", href: "/roster" },
  { label: "Leave", href: "/leave" },
  { label: "Checklists", href: "/checklists" },
  { label: "Leaderboard", href: "/leaderboard" },
];

/** Shared tab row for every /staff/* sub-page — accounts.StaffRole's own
 * page.tsx stays the "Roles" tab unchanged; these are siblings, not a
 * replacement.
 */
export function StaffTabs() {
  const { gymId } = useParams<{ gymId: string }>();
  const pathname = usePathname();
  const base = `/${gymId}/staff`;

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
