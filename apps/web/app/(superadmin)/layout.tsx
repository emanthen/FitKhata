"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth";

const NAV_ITEMS = [
  { label: "Tenants", href: "/platform/tenants" },
  { label: "Metrics", href: "/platform/metrics" },
  { label: "Feature flags", href: "/platform/feature-flags" },
  { label: "Announcements", href: "/platform/announcements" },
  { label: "Tickets", href: "/platform/tickets" },
];

export default function SuperAdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { claims, ready, logout } = useAuth();

  if (!ready) return null;

  if (!claims?.is_platform_staff) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6 text-center">
        <p className="text-sm opacity-70">
          This area is for FitKhata platform staff only.
        </p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 flex-col justify-between border-r p-4">
        <div className="space-y-4">
          <p className="px-2 text-sm font-semibold">FitKhata Platform</p>
          <nav className="space-y-1">
            {NAV_ITEMS.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
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
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
