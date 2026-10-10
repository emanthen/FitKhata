"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { tokenStore } from "@fitkhata/api-client";

import { useAuth } from "@/lib/auth";
import { BranchSwitcher } from "@/components/branch-switcher";
import { ReadOnlyBanner } from "@/components/saas/read-only-banner";
import { ImpersonationBanner } from "@/components/saas/impersonation-banner";

const NAV_ITEMS: { label: string; href: string; minRole: string | null }[] = [
  { label: "Dashboard", href: "", minRole: null },
  { label: "Members", href: "/members", minRole: "front_desk" },
  { label: "Call queue", href: "/retention/queue", minRole: "front_desk" },
  { label: "Retention", href: "/retention", minRole: "front_desk" },
  { label: "Staff", href: "/staff", minRole: "manager" },
  { label: "Reports", href: "/reports", minRole: "manager" },
  { label: "Settings", href: "/settings", minRole: "owner" },
];

const ROLE_RANK: Record<string, number> = { owner: 3, manager: 2, front_desk: 1, trainer: 0 };

function canSee(role: string | null, minRole: string | null): boolean {
  if (minRole === null) return true;
  if (role === null) return false;
  return (ROLE_RANK[role] ?? -1) >= (ROLE_RANK[minRole] ?? 99);
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { gymId } = useParams<{ gymId: string }>();
  const pathname = usePathname();
  const { claims, ready, logout } = useAuth();

  useEffect(() => {
    // Direct navigation/bookmark/shared link — make sure X-Gym-Id matches
    // the URL, not whatever was last active.
    tokenStore.setActiveGymId(gymId);
  }, [gymId]);

  if (!ready) return null;

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 flex-col justify-between border-r p-4">
        <div className="space-y-4">
          <BranchSwitcher activeGymId={gymId} />
          <nav className="space-y-1">
            {NAV_ITEMS.filter((item) => canSee(claims?.role ?? null, item.minRole)).map((item) => {
              const href = `/${gymId}${item.href}`;
              const active = pathname === href;
              return (
                <Link
                  key={item.href}
                  href={href}
                  className={`block rounded px-2 py-1.5 text-sm ${active ? "bg-neutral-100 font-medium dark:bg-neutral-800" : "opacity-70 hover:opacity-100"}`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
        <button onClick={logout} className="text-left text-sm opacity-60 hover:opacity-100">
          Sign out
        </button>
      </aside>
      <main className="flex-1 p-6">
        <ImpersonationBanner />
        <ReadOnlyBanner />
        {children}
      </main>
    </div>
  );
}
