import Link from "next/link";

import { RedListWidget } from "@/components/red-list-widget";

export default async function GymDashboardPage({
  params,
}: {
  params: Promise<{ gymId: string }>;
}) {
  const { gymId } = await params;
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Gym {gymId}</h1>
      <RedListWidget />
      <div className="flex gap-4 text-sm">
        <Link href={`/${gymId}/coaching`} className="text-blue-600 hover:underline">
          Coaching
        </Link>
        <Link href={`/${gymId}/coaching/insights`} className="text-blue-600 hover:underline">
          AI insights
        </Link>
      </div>
    </div>
  );
}
