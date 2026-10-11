import Image from "next/image";

import { Logo } from "@/components/logo";
import heroImage from "@/public/images/marketing/hero-checkin.jpg";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-dashboard grid min-h-screen md:grid-cols-2">
      <div className="relative hidden md:block">
        <Image src={heroImage} alt="" fill priority sizes="50vw" className="object-cover" />
        <div className="absolute inset-0 bg-gradient-to-t from-primary/90 via-primary/40 to-primary/10" />
        <div className="absolute inset-0 flex flex-col justify-between p-10">
          <div className="text-white">
            <Logo size={26} />
          </div>
          <p className="max-w-xs text-sm text-white/90">
            Check-ins, billing, staff payroll and member retention, in one place.
          </p>
        </div>
      </div>

      <main className="flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-sm">{children}</div>
      </main>
    </div>
  );
}
