"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getMember, listInvoices, listMemberships, type Membership, type Page } from "@fitkhata/api-client";
import type { Invoice } from "@fitkhata/api-client";

import { Badge } from "@/components/ui/badge";
import { formatNpr } from "@/lib/money";

export default function MemberProfilePage() {
  const { memberId } = useParams<{ memberId: string }>();

  const member = useQuery({ queryKey: ["member", memberId], queryFn: () => getMember(memberId) });
  const memberships = useQuery({
    queryKey: ["memberships", memberId],
    queryFn: () => listMemberships(memberId),
  });
  const invoices = useQuery({
    queryKey: ["invoices", memberId],
    queryFn: () => listInvoices(memberId),
  });

  if (member.isLoading || !member.data) return <p className="text-sm opacity-60">Loading...</p>;

  const m = member.data;
  const membershipList: Membership[] = Array.isArray(memberships.data)
    ? memberships.data
    : ((memberships.data as Page<Membership> | undefined)?.results ?? []);
  const invoiceList: Invoice[] = Array.isArray(invoices.data)
    ? invoices.data
    : ((invoices.data as Page<Invoice> | undefined)?.results ?? []);

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{m.full_name}</h1>
        <p className="text-sm opacity-60">
          {m.member_code} · {m.phone}
        </p>
        <div className="mt-2 flex gap-2">
          <Badge variant="secondary">{m.status}</Badge>
          {m.risk_state !== "normal" && (
            <Badge variant={m.risk_state === "red_list" ? "destructive" : "secondary"}>
              {m.risk_state}
            </Badge>
          )}
          {m.tags.map((tag) => (
            <Badge key={tag} variant="outline">
              {tag}
            </Badge>
          ))}
        </div>
      </div>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">Memberships</h2>
        <ul className="space-y-1 text-sm">
          {membershipList.map((ms) => (
            <li key={ms.id} className="flex justify-between rounded border px-3 py-2">
              <span>
                {ms.start_date} → {ms.expiry_date}
              </span>
              <Badge variant="secondary">{ms.status}</Badge>
            </li>
          ))}
          {membershipList.length === 0 && (
            <li className="text-sm opacity-60">No memberships yet.</li>
          )}
        </ul>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-medium">Dues</h2>
        <ul className="space-y-1 text-sm">
          {invoiceList.map((inv) => (
            <li key={inv.id} className="flex justify-between rounded border px-3 py-2">
              <span className="font-mono text-xs">{inv.number}</span>
              <span>
                {formatNpr(inv.total_npr, { symbol: true })}{" "}
                <span className="opacity-60">({inv.status})</span>
              </span>
            </li>
          ))}
          {invoiceList.length === 0 && <li className="text-sm opacity-60">No invoices yet.</li>}
        </ul>
      </section>
    </div>
  );
}
