"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { listMembers, type Member, type Page } from "@fitkhata/api-client";
import { ArrowRight, TriangleAlert } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";

export function RedListWidget() {
  const { gymId } = useParams<{ gymId: string }>();
  const query = useQuery({
    queryKey: ["members", "red-list-widget"],
    queryFn: () => listMembers({ risk_state: "red_list" }) as Promise<Page<Member> | Member[]>,
  });

  const members = query.data
    ? Array.isArray(query.data)
      ? query.data
      : query.data.results
    : [];

  return (
    <Link
      href={`/${gymId}/members?risk_state=red_list`}
      className="block w-full max-w-sm rounded-xl border border-destructive/30 bg-destructive/5 p-4 transition-colors hover:border-destructive/50"
    >
      <div className="flex items-center gap-1.5 text-destructive">
        <TriangleAlert size={14} strokeWidth={2} />
        <p className="text-xs font-medium">Red list</p>
      </div>

      {query.isLoading ? (
        <Skeleton className="mt-2 h-8 w-10" />
      ) : (
        <p className="font-dashboard-mono mt-1 text-3xl font-semibold text-destructive tabular-nums">
          {members.length}
        </p>
      )}

      <ul className="mt-2 space-y-0.5 text-sm text-foreground/80">
        {members.slice(0, 5).map((member) => (
          <li key={member.id} className="truncate">
            {member.full_name}
          </li>
        ))}
      </ul>

      {members.length > 5 && (
        <p className="mt-1.5 flex items-center gap-1 text-xs text-destructive">
          +{members.length - 5} more <ArrowRight size={12} strokeWidth={2} />
        </p>
      )}
      {members.length === 0 && !query.isLoading && (
        <p className="mt-2 text-sm text-muted-foreground">Nobody on the red list.</p>
      )}
    </Link>
  );
}
