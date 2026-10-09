"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { listMembers, type Member, type Page } from "@fitkhata/api-client";

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
      className="block w-full max-w-sm rounded border border-red-200 bg-red-50 p-4 transition-colors hover:border-red-300 dark:border-red-900 dark:bg-red-950"
    >
      <p className="text-sm font-medium text-red-700 dark:text-red-400">Red list</p>
      <p className="text-3xl font-semibold text-red-900 dark:text-red-200">
        {query.isLoading ? "..." : members.length}
      </p>
      <ul className="mt-2 space-y-0.5 text-sm text-red-800 dark:text-red-300">
        {members.slice(0, 5).map((member) => (
          <li key={member.id} className="truncate">
            {member.full_name}
          </li>
        ))}
      </ul>
      {members.length > 5 && (
        <p className="mt-1 text-xs text-red-600 dark:text-red-400">
          +{members.length - 5} more &rarr;
        </p>
      )}
      {members.length === 0 && !query.isLoading && (
        <p className="mt-2 text-sm text-red-600 dark:text-red-400">Nobody on the red list.</p>
      )}
    </Link>
  );
}
