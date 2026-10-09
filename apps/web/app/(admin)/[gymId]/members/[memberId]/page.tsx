"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  approveCreditNote,
  collectPayment,
  createCreditNote,
  fetchInvoicePdf,
  getMember,
  listCreditNotes,
  listInvoices,
  listMemberships,
  sendReceiptSms,
  voidInvoice,
  type CreditNote,
  type Membership,
  type Page,
  type PaymentMode,
} from "@fitkhata/api-client";
import type { Invoice } from "@fitkhata/api-client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth";
import { formatNpr } from "@/lib/money";

const DESK_PAYMENT_MODES: { value: PaymentMode; label: string }[] = [
  { value: "cash", label: "Cash" },
  { value: "manual_esewa", label: "Manual eSewa" },
  { value: "bank", label: "Bank transfer" },
  { value: "cheque", label: "Cheque" },
];

export default function MemberProfilePage() {
  const { memberId } = useParams<{ memberId: string }>();
  const queryClient = useQueryClient();
  const { claims } = useAuth();
  const isOwner = claims?.role === "owner";

  const member = useQuery({ queryKey: ["member", memberId], queryFn: () => getMember(memberId) });
  const memberships = useQuery({
    queryKey: ["memberships", memberId],
    queryFn: () => listMemberships(memberId),
  });
  const invoices = useQuery({
    queryKey: ["invoices", memberId],
    queryFn: () => listInvoices(memberId),
  });
  const creditNotes = useQuery({
    queryKey: ["credit-notes"],
    queryFn: listCreditNotes,
    enabled: isOwner,
  });

  const [openPanel, setOpenPanel] = useState<{ invoiceId: string; kind: "pay" | "void" | "cn" } | null>(
    null
  );

  function invalidateInvoices() {
    queryClient.invalidateQueries({ queryKey: ["invoices", memberId] });
    queryClient.invalidateQueries({ queryKey: ["credit-notes"] });
  }

  if (member.isLoading || !member.data) return <p className="text-sm opacity-60">Loading...</p>;

  const m = member.data;
  const membershipList: Membership[] = Array.isArray(memberships.data)
    ? memberships.data
    : ((memberships.data as Page<Membership> | undefined)?.results ?? []);
  const invoiceList: Invoice[] = Array.isArray(invoices.data)
    ? invoices.data
    : ((invoices.data as Page<Invoice> | undefined)?.results ?? []);
  const creditNoteList: CreditNote[] = Array.isArray(creditNotes.data)
    ? creditNotes.data
    : ((creditNotes.data as Page<CreditNote> | undefined)?.results ?? []);

  async function openPdf(invoiceId: string) {
    const blob = await fetchInvoicePdf(invoiceId);
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }

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
        <h2 className="text-lg font-medium">Invoices &amp; dues</h2>
        <ul className="space-y-2 text-sm">
          {invoiceList.map((inv) => {
            const pendingNotes = creditNoteList.filter(
              (cn) => cn.invoice === inv.id && !cn.approved_by
            );
            const panelOpen = openPanel?.invoiceId === inv.id ? openPanel.kind : null;

            return (
              <li key={inv.id} className="rounded border px-3 py-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs">{inv.number}</span>
                  <span>
                    {formatNpr(inv.total_npr, { symbol: true })}{" "}
                    <span className="opacity-60">({inv.status})</span>
                  </span>
                </div>

                <div className="mt-2 flex flex-wrap gap-3 text-xs">
                  <button
                    className="text-blue-600 hover:underline"
                    onClick={() => openPdf(inv.id)}
                  >
                    PDF
                  </button>
                  <button
                    className="text-blue-600 hover:underline"
                    onClick={() => sendReceiptSms(inv.id)}
                  >
                    SMS receipt
                  </button>
                  {inv.status === "draft" && (
                    <button
                      className="text-blue-600 hover:underline"
                      onClick={() => setOpenPanel({ invoiceId: inv.id, kind: "pay" })}
                    >
                      Collect payment
                    </button>
                  )}
                  {inv.status === "issued" && (
                    <button
                      className="text-blue-600 hover:underline"
                      onClick={() => setOpenPanel({ invoiceId: inv.id, kind: "cn" })}
                    >
                      Request credit note
                    </button>
                  )}
                  {isOwner && inv.status !== "void" && (
                    <button
                      className="text-red-600 hover:underline"
                      onClick={() => setOpenPanel({ invoiceId: inv.id, kind: "void" })}
                    >
                      Void
                    </button>
                  )}
                </div>

                {panelOpen === "pay" && (
                  <CollectPaymentForm
                    invoiceId={inv.id}
                    defaultAmount={inv.total_npr}
                    onDone={() => {
                      setOpenPanel(null);
                      invalidateInvoices();
                    }}
                    onCancel={() => setOpenPanel(null)}
                  />
                )}
                {panelOpen === "void" && (
                  <VoidForm
                    invoiceId={inv.id}
                    onDone={() => {
                      setOpenPanel(null);
                      invalidateInvoices();
                    }}
                    onCancel={() => setOpenPanel(null)}
                  />
                )}
                {panelOpen === "cn" && (
                  <CreditNoteForm
                    invoiceId={inv.id}
                    onDone={() => {
                      setOpenPanel(null);
                      invalidateInvoices();
                    }}
                    onCancel={() => setOpenPanel(null)}
                  />
                )}

                {isOwner && pendingNotes.length > 0 && (
                  <ul className="mt-2 space-y-1 border-t pt-2">
                    {pendingNotes.map((cn) => (
                      <li key={cn.id} className="flex items-center justify-between text-xs">
                        <span>
                          {formatNpr(cn.amount_npr, { symbol: true })} — {cn.reason}
                        </span>
                        <button
                          className="text-green-700 hover:underline"
                          onClick={async () => {
                            await approveCreditNote(cn.id);
                            invalidateInvoices();
                          }}
                        >
                          Approve
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
          {invoiceList.length === 0 && <li className="text-sm opacity-60">No invoices yet.</li>}
        </ul>
      </section>
    </div>
  );
}

function CollectPaymentForm({
  invoiceId,
  defaultAmount,
  onDone,
  onCancel,
}: {
  invoiceId: string;
  defaultAmount: string;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [mode, setMode] = useState<PaymentMode>("cash");
  const [amount, setAmount] = useState(defaultAmount);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await collectPayment({
        invoice_id: invoiceId,
        mode: mode as "cash" | "manual_esewa" | "bank" | "cheque",
        amount_npr: amount,
      });
      onDone();
    } catch {
      setError("Couldn't record this payment.");
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-2 flex flex-wrap items-end gap-2 border-t pt-2">
      {error && <p className="w-full text-xs text-red-600">{error}</p>}
      <select
        value={mode}
        onChange={(e) => setMode(e.target.value as PaymentMode)}
        className="h-8 rounded border px-2 text-xs"
      >
        {DESK_PAYMENT_MODES.map((m) => (
          <option key={m.value} value={m.value}>
            {m.label}
          </option>
        ))}
      </select>
      <Input
        type="number"
        step="0.01"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        className="h-8 w-28 text-xs"
        required
      />
      <Button type="submit" size="sm" disabled={submitting}>
        {submitting ? "..." : "Confirm"}
      </Button>
      <button type="button" className="text-xs opacity-60 hover:underline" onClick={onCancel}>
        Cancel
      </button>
    </form>
  );
}

function VoidForm({
  invoiceId,
  onDone,
  onCancel,
}: {
  invoiceId: string;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await voidInvoice(invoiceId, reason);
      onDone();
    } catch {
      setError("Couldn't void this invoice.");
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-2 flex flex-wrap items-end gap-2 border-t pt-2">
      {error && <p className="w-full text-xs text-red-600">{error}</p>}
      <Input
        placeholder="Reason for voiding"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        className="h-8 flex-1 text-xs"
        required
      />
      <Button type="submit" size="sm" variant="destructive" disabled={submitting}>
        {submitting ? "..." : "Void"}
      </Button>
      <button type="button" className="text-xs opacity-60 hover:underline" onClick={onCancel}>
        Cancel
      </button>
    </form>
  );
}

function CreditNoteForm({
  invoiceId,
  onDone,
  onCancel,
}: {
  invoiceId: string;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await createCreditNote({ invoice: invoiceId, amount_npr: amount, reason });
      onDone();
    } catch {
      setError("Couldn't submit this credit note.");
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-2 flex flex-wrap items-end gap-2 border-t pt-2">
      {error && <p className="w-full text-xs text-red-600">{error}</p>}
      <Input
        type="number"
        step="0.01"
        placeholder="Amount"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        className="h-8 w-28 text-xs"
        required
      />
      <Input
        placeholder="Reason"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        className="h-8 flex-1 text-xs"
        required
      />
      <Button type="submit" size="sm" disabled={submitting}>
        {submitting ? "..." : "Submit for approval"}
      </Button>
      <button type="button" className="text-xs opacity-60 hover:underline" onClick={onCancel}>
        Cancel
      </button>
    </form>
  );
}
