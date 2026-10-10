import { MarketingNav } from "@/components/marketing/nav";
import { MarketingFooter } from "@/components/marketing/footer";

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="surface-marketing font-marketing min-h-[100dvh]">
      <MarketingNav />
      {children}
      <MarketingFooter />
    </div>
  );
}
