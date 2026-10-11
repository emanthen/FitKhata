"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, Building2, Flag, LifeBuoy, LineChart, LogOut, UserPlus } from "lucide-react";

import { useAuth } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const NAV_ITEMS = [
  { label: "Tenants", href: "/platform/tenants", icon: Building2 },
  { label: "Metrics", href: "/platform/metrics", icon: LineChart },
  { label: "Feature flags", href: "/platform/feature-flags", icon: Flag },
  { label: "Leads", href: "/platform/leads", icon: UserPlus },
  { label: "Announcements", href: "/platform/announcements", icon: Bell },
  { label: "Tickets", href: "/platform/tickets", icon: LifeBuoy },
];

export default function SuperAdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { claims, ready, logout } = useAuth();

  if (!ready) return null;

  if (!claims?.is_platform_staff) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6 text-center">
        <p className="text-sm text-muted-foreground">
          This area is for FitKhata platform staff only.
        </p>
      </div>
    );
  }

  return (
    // Locked dark mode, regardless of the viewer's system/app theme — a
    // platform console pretending to be a tenant's own admin (or vice
    // versa) is a real risk given the impersonation flow this layout
    // guards, so it stays visually unmistakable rather than following
    // next-themes.
    <div className="dark font-dashboard flex min-h-screen bg-background text-foreground">
      <aside className="flex w-56 shrink-0 flex-col justify-between border-r p-4">
        <div className="space-y-5">
          <div className="flex items-center gap-2 px-1">
            <span className="bg-primary size-2.5 rounded-sm" />
            <span className="text-sm font-semibold tracking-tight">FitKhata</span>
            <Badge variant="outline" className="ml-auto border-accent/40 text-accent">
              PLATFORM
            </Badge>
          </div>
          <nav className="space-y-0.5">
            {NAV_ITEMS.map((item) => {
              const active = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors ${
                    active
                      ? "bg-primary/10 font-medium text-primary"
                      : "text-foreground/70 hover:bg-muted hover:text-foreground"
                  }`}
                >
                  <Icon size={16} strokeWidth={2} />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
        <Button variant="ghost" size="sm" onClick={logout} className="justify-start text-muted-foreground">
          <LogOut size={14} strokeWidth={2} data-icon="inline-start" />
          Sign out
        </Button>
      </aside>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
