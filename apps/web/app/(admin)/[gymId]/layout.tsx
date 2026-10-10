"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { tokenStore } from "@fitkhata/api-client";
import {
  Bell,
  BarChart3,
  CreditCard,
  Dumbbell,
  IdCard,
  LogOut,
  Menu,
  PhoneCall,
  Settings,
  Target,
  User,
  Users,
  LayoutDashboard,
} from "lucide-react";

import { useAuth } from "@/lib/auth";
import { Logo } from "@/components/logo";
import { BranchSwitcher } from "@/components/branch-switcher";
import { ReadOnlyBanner } from "@/components/saas/read-only-banner";
import { ImpersonationBanner } from "@/components/saas/impersonation-banner";
import { ThemeToggle } from "@/components/theme-toggle";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

type NavItem = { label: string; href: string; minRole: string | null; icon: React.ElementType };

const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "", minRole: null, icon: LayoutDashboard },
  { label: "Members", href: "/members", minRole: "front_desk", icon: Users },
  { label: "Call queue", href: "/retention/queue", minRole: "front_desk", icon: PhoneCall },
  { label: "Retention", href: "/retention", minRole: "front_desk", icon: Target },
  { label: "Coaching", href: "/coaching", minRole: "front_desk", icon: Dumbbell },
  { label: "Billing", href: "/billing/shift", minRole: "front_desk", icon: CreditCard },
  { label: "Staff", href: "/staff", minRole: "manager", icon: IdCard },
  { label: "Reports", href: "/reports", minRole: "manager", icon: BarChart3 },
  { label: "Notifications", href: "/notifications/log", minRole: "manager", icon: Bell },
  { label: "Settings", href: "/settings", minRole: "owner", icon: Settings },
];

const ROLE_RANK: Record<string, number> = { owner: 3, manager: 2, front_desk: 1, trainer: 0 };

function canSee(role: string | null, minRole: string | null): boolean {
  if (minRole === null) return true;
  if (role === null) return false;
  return (ROLE_RANK[role] ?? -1) >= (ROLE_RANK[minRole] ?? 99);
}

function NavLinks({ gymId, onNavigate }: { gymId: string; onNavigate?: () => void }) {
  const pathname = usePathname();
  const { claims } = useAuth();

  return (
    <nav className="flex flex-col gap-0.5">
      {NAV_ITEMS.filter((item) => canSee(claims?.role ?? null, item.minRole)).map((item) => {
        const href = `/${gymId}${item.href}`;
        const active = pathname === href;
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={href}
            onClick={onNavigate}
            className={`flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors ${
              active
                ? "bg-primary/10 font-medium text-primary"
                : "text-foreground/70 hover:bg-muted hover:text-foreground"
            }`}
          >
            <Icon size={18} strokeWidth={active ? 2.5 : 2} />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { gymId } = useParams<{ gymId: string }>();
  const { claims, ready, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    // Direct navigation/bookmark/shared link — make sure X-Gym-Id matches
    // the URL, not whatever was last active.
    tokenStore.setActiveGymId(gymId);
  }, [gymId]);

  if (!ready) return null;

  return (
    <div className="font-dashboard flex min-h-[100dvh]">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 flex-col border-r bg-sidebar p-4 md:flex">
        <div className="mb-5 px-1">
          <Logo size={24} />
        </div>
        <div className="mb-4">
          <BranchSwitcher activeGymId={gymId} />
        </div>
        <NavLinks gymId={gymId} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Topbar */}
        <header className="flex h-14 items-center justify-between border-b px-4 md:px-6">
          <div className="flex items-center gap-3 md:hidden">
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" aria-label="Open navigation">
                  <Menu size={20} />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-64 p-4">
                <SheetTitle asChild>
                  <div className="mb-5">
                    <Logo size={24} />
                  </div>
                </SheetTitle>
                <div className="mb-4">
                  <BranchSwitcher activeGymId={gymId} />
                </div>
                <NavLinks gymId={gymId} onNavigate={() => setMobileOpen(false)} />
              </SheetContent>
            </Sheet>
            <span className="text-sm font-semibold">FitKhata</span>
          </div>
          <div className="hidden md:block" />
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  className="ml-1 flex items-center gap-2 rounded-full p-0.5 outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label="Account menu"
                >
                  <Avatar className="size-8">
                    <AvatarFallback className="bg-primary text-primary-foreground">
                      <User size={16} />
                    </AvatarFallback>
                  </Avatar>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                <div className="px-2 py-1.5">
                  <p className="text-sm font-medium capitalize">{claims?.role ?? "Staff"}</p>
                </div>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={logout} className="text-destructive">
                  <LogOut size={16} className="mr-2" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <main className="min-w-0 flex-1 p-4 md:p-6">
          <ImpersonationBanner />
          <ReadOnlyBanner />
          {children}
        </main>
      </div>
    </div>
  );
}
