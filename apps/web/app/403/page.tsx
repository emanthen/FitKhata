import Link from "next/link";

export default function ForbiddenPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col items-center justify-center space-y-4 px-4 text-center">
      <h1 className="text-3xl font-bold">403</h1>
      <p className="opacity-70">
        You don&apos;t have permission to do that. Switch to a branch where you have a role that
        allows it, or ask an owner/manager to grant you one.
      </p>
      <Link href="/" className="rounded bg-black px-4 py-2 text-white">
        Back home
      </Link>
    </main>
  );
}
