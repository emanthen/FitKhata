"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getRetentionDashboard } from "@fitkhata/api-client";
import { Banknote, PhoneCall, Shield, Snowflake, Target } from "lucide-react";

import { Button } from "@/components/ui/button";
import { StatTile } from "@/components/stat-tile";
import { formatNpr } from "@/lib/money";

export default function RetentionDashboardPage() {
  const { gymId } = useParams<{ gymId: string }>();
  const query = useQuery({
    queryKey: ["retention", "dashboard"],
    queryFn: () => getRetentionDashboard(),
  });

  return (
    <div className="max-w-2xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <Target size={18} strokeWidth={2} className="text-primary" />
          Retention
        </h1>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href={`/${gymId}/retention/queue`}>
              <PhoneCall size={13} strokeWidth={2} data-icon="inline-start" />
              Call queue
            </Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link href={`/${gymId}/retention/freeze`}>
              <Snowflake size={13} strokeWidth={2} data-icon="inline-start" />
              Freeze wizard
            </Link>
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <StatTile
          label="Churn rate this month"
          icon={<Target size={16} strokeWidth={2} />}
          loading={query.isLoading}
          value={query.data ? `${(query.data.churn_rate * 100).toFixed(1)}%` : "0%"}
        />
        <StatTile
          label="Saves this month"
          icon={<Shield size={16} strokeWidth={2} />}
          loading={query.isLoading}
          value={String(query.data?.saves_this_month ?? 0)}
        />
        <StatTile
          label="Revenue protected"
          icon={<Banknote size={16} strokeWidth={2} />}
          loading={query.isLoading}
          value={formatNpr(query.data?.revenue_protected_npr ?? "0", { symbol: true })}
        />
      </div>
    </div>
  );
}
