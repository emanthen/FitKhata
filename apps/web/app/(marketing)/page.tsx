import { MarketingHero } from "@/components/marketing/hero";
import { MarketingFeatures } from "@/components/marketing/features";
import { MarketingCredibility } from "@/components/marketing/credibility";
import { MarketingPricing } from "@/components/marketing/pricing";
import { MarketingCtaBand } from "@/components/marketing/cta-band";

export default function MarketingHomePage() {
  return (
    <>
      <MarketingHero />
      <MarketingFeatures />
      <MarketingCredibility />
      <MarketingPricing />
      <MarketingCtaBand />
    </>
  );
}
