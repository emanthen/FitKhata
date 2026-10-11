import Link from "next/link";
import { ShieldAlert } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function ForbiddenPage() {
  return (
    <main className="font-dashboard mx-auto flex min-h-screen max-w-sm flex-col items-center justify-center space-y-4 px-4 text-center">
      <ShieldAlert size={32} strokeWidth={1.75} className="text-destructive" />
      <h1 className="text-2xl font-bold tracking-tight">403</h1>
      <p className="text-sm text-muted-foreground">
        You don&apos;t have permission to do that. Switch to a branch where you have a role that
        allows it, or ask an owner/manager to grant you one.
      </p>
      <Button asChild>
        <Link href="/">Back home</Link>
      </Button>
    </main>
  );
}
