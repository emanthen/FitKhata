"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { listMembers, type Member, type Page } from "@fitkhata/api-client";
import { Search, UserPlus, UserRoundX, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { RegisterDrawer } from "@/components/members/register-drawer";

function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}

export default function MembersPage() {
  const { gymId } = useParams<{ gymId: string }>();
  const searchParams = useSearchParams();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<string>("");
  // Pre-filled from a deep link (e.g. the dashboard's Red List widget) --
  // only read once on mount, the Select above is what drives it after that.
  const [riskState, setRiskState] = useState<string>(() => searchParams.get("risk_state") ?? "");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const debouncedQ = useDebounced(q, 300);

  const searchQuery = useQuery({
    queryKey: ["members", "search", debouncedQ],
    queryFn: () => listMembers({ q: debouncedQ }) as Promise<Member[]>,
    enabled: debouncedQ.trim().length > 0,
  });

  const browseQuery = useInfiniteQuery({
    queryKey: ["members", "browse", status, riskState],
    queryFn: ({ pageParam }: { pageParam: string | undefined }) =>
      listMembers({ status: status || undefined, risk_state: riskState || undefined, cursor: pageParam }) as Promise<
        Page<Member>
      >,
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => {
      if (!lastPage.next) return undefined;
      return new URL(lastPage.next).searchParams.get("cursor") ?? undefined;
    },
    enabled: debouncedQ.trim().length === 0,
  });

  const searching = debouncedQ.trim().length > 0;
  const members: Member[] = searching
    ? (searchQuery.data ?? [])
    : (browseQuery.data?.pages.flatMap((p) => p.results) ?? []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold tracking-tight">Members</h1>
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <Link href={`/${gymId}/members/import`}>
              <Upload size={15} strokeWidth={2} data-icon="inline-start" />
              Import
            </Link>
          </Button>
          <Button onClick={() => setDrawerOpen(true)}>
            <UserPlus size={15} strokeWidth={2} data-icon="inline-start" />
            Register member
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <div className="relative max-w-xs flex-1">
          <Search
            size={14}
            strokeWidth={2}
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            placeholder="Search by name, phone, or member code..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="pl-8"
          />
        </div>
        <Select value={status || "all"} onValueChange={(v) => setStatus(v === "all" ? "" : v)}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="expired">Expired</SelectItem>
            <SelectItem value="frozen">Frozen</SelectItem>
            <SelectItem value="cancelled">Cancelled</SelectItem>
            <SelectItem value="trial">Trial</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={riskState || "all"}
          onValueChange={(v) => setRiskState(v === "all" ? "" : v)}
        >
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Risk" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All risk states</SelectItem>
            <SelectItem value="normal">Normal</SelectItem>
            <SelectItem value="warning">Warning</SelectItem>
            <SelectItem value="red_list">Red list</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Code</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Phone</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Risk</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(searching ? searchQuery.isLoading : browseQuery.isLoading) &&
            Array.from({ length: 6 }).map((_, i) => (
              <TableRow key={`skeleton-${i}`}>
                <TableCell colSpan={5}>
                  <Skeleton className="h-5 w-full" />
                </TableCell>
              </TableRow>
            ))}
          {members.map((m) => (
            <TableRow key={m.id}>
              <TableCell className="font-dashboard-mono text-xs">{m.member_code}</TableCell>
              <TableCell>
                <Link href={`/${gymId}/members/${m.id}`} className="font-medium hover:underline">
                  {m.full_name}
                </Link>
              </TableCell>
              <TableCell className="font-dashboard-mono text-sm">{m.phone}</TableCell>
              <TableCell>
                <Badge variant="secondary">{m.status}</Badge>
              </TableCell>
              <TableCell>
                {m.risk_state !== "normal" && (
                  <Badge variant={m.risk_state === "red_list" ? "destructive" : "secondary"}>
                    {m.risk_state}
                  </Badge>
                )}
              </TableCell>
            </TableRow>
          ))}
          {members.length === 0 && !(searching ? searchQuery.isLoading : browseQuery.isLoading) && (
            <TableRow>
              <TableCell colSpan={5} className="py-12 text-center">
                <div className="flex flex-col items-center gap-2 text-muted-foreground">
                  <UserRoundX size={22} strokeWidth={1.75} />
                  <p className="text-sm">No members found.</p>
                </div>
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {!searching && browseQuery.hasNextPage && (
        <Button
          variant="outline"
          onClick={() => browseQuery.fetchNextPage()}
          disabled={browseQuery.isFetchingNextPage}
        >
          {browseQuery.isFetchingNextPage ? "Loading..." : "Load more"}
        </Button>
      )}

      <RegisterDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        onRegistered={() => {
          searchQuery.refetch();
          browseQuery.refetch();
        }}
      />
    </div>
  );
}
