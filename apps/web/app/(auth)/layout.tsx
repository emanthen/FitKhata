export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="font-dashboard mx-auto flex min-h-screen max-w-sm items-center px-4">
      {children}
    </main>
  );
}
