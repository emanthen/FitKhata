export default function GateLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="font-dashboard flex min-h-screen items-center justify-center">{children}</main>
  );
}
