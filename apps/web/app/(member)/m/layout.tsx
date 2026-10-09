import type { Metadata } from "next";
import { AnnouncementBanner } from "@/components/member/announcement-banner";
import { UpdateToast } from "@/components/member/update-toast";

// A nested MetadataRoute manifest (app/(member)/m/manifest.ts) is only
// actually linked on the page if this layout's own metadata says so — Next
// auto-injects the <link rel="manifest"> for a ROOT app/manifest.ts only.
export const metadata: Metadata = {
  manifest: "/m/manifest.webmanifest",
};

export default function MemberLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto max-w-md px-4 py-8">
      <AnnouncementBanner />
      {children}
      <UpdateToast />
    </main>
  );
}
