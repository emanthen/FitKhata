"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
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
import { Check, FileText, MessageSquareText, Printer, Receipt, Wallet, X } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getBridgePrintConfig, printReceiptViaBridge } from "@/lib/bridge-print";
import { useAuth } from "@/lib/auth";
import { formatNpr } from "@/lib/money";

const DESK_PAYMENT_MODES: { value: PaymentMode; labelKey: string }[] = [
  { value: "cash", labelKey: "membersPaymentModeCash" },
  { value: "manual_esewa", labelKey: "membersPaymentModeManualEsewa" },
  { value: "bank", labelKey: "membersPaymentModeBank" },
  { value: "cheque", labelKey: "membersPaymentModeCheque" },
];

const STATUS_KEY: Record<string, string> = {
  active: "membersStatusActive",
  expired: "membersStatusExpired",
  frozen: "membersStatusFrozen",
  cancelled: "membersStatusCancelled",
  trial: "membersStatusTrial",
};

const RISK_KEY: Record<string, string> = {
  normal: "membersRiskNormal",
  warning: "membersRiskWarning",
  red_list: "membersRiskRedList",
};

const MEMBERSHIP_STATUS_KEY: Record<string, string> = {
  active: "membersMembershipStatusActive",
  expired: "membersMembershipStatusExpired",
  paused: "membersMembershipStatusPaused",
  cancelled: "membersMembershipStatusCancelled",
};

const INVOICE_STATUS_KEY: Record<string, string> = {
  draft: "membersInvoiceStatusDraft",
  issued: "membersInvoiceStatusIssued",
  void: "membersInvoiceStatusVoid",
};

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase();
}

export default function MemberProfilePage() {
  const { memberId } = useParams<{ memberId: string }>();
  const t = useTranslations("admin");
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
  const [bridgeReady, setBridgeReady] = useState(false);
  const [printingId, setPrintingId] = useState<string | null>(null);
  const [printError, setPrintError] = useState<string | null>(null);

  useEffect(() => {
    setBridgeReady(getBridgePrintConfig() !== null);
  }, []);

  function invalidateInvoices() {
    queryClient.invalidateQueries({ queryKey: ["invoices", memberId] });
    queryClient.invalidateQueries({ queryKey: ["credit-notes"] });
  }

  if (member.isLoading || !member.data) {
    return (
      <div className="max-w-2xl space-y-6">
        <div className="flex items-center gap-3">
          <Skeleton className="size-12 rounded-full" />
          <div className="space-y-2">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-4 w-28" />
          </div>
        </div>
        <Skeleton className="h-32 w-full rounded-xl" />
      </div>
    );
  }

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

  async function printToThermalPrinter(inv: Invoice) {
    setPrintError(null);
    setPrintingId(inv.id);
    try {
      await printReceiptViaBridge({
        gymName: "FitKhata", // this page doesn't have the gym's own display name in scope yet
        titleNe: "रसिद",
        lines: inv.lines.map((l) => ({
          label: `${l.description} x${l.quantity}`,
          value: formatNpr(l.line_total_npr),
        })),
        totalNpr: formatNpr(inv.total_npr, { symbol: true }),
      });
    } catch (err) {
      setPrintError(err instanceof Error ? err.message : t("membersPrintFailed"));
    } finally {
      setPrintingId(null);
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center gap-3">
        <Avatar className="size-12">
          <AvatarFallback className="bg-primary text-primary-foreground">
            {initials(m.full_name)}
          </AvatarFallback>
        </Avatar>
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{m.full_name}</h1>
          <p className="font-dashboard-mono text-sm text-muted-foreground">
            {m.member_code} · {m.phone}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <Badge variant="secondary">{t(STATUS_KEY[m.status] ?? "membersStatusActive")}</Badge>
        {m.risk_state !== "normal" && (
          <Badge variant={m.risk_state === "red_list" ? "destructive" : "secondary"}>
            {t(RISK_KEY[m.risk_state] ?? "membersRiskNormal")}
          </Badge>
        )}
        {m.tags.map((tag) => (
          <Badge key={tag} variant="outline">
            {tag}
          </Badge>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("membersMembershipsTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="divide-y">
            {membershipList.map((ms) => (
              <li key={ms.id} className="flex items-center justify-between py-2.5 text-sm">
                <span className="font-dashboard-mono">
                  {ms.start_date} &rarr; {ms.expiry_date}
                </span>
                <Badge variant="secondary">
                  {t(MEMBERSHIP_STATUS_KEY[ms.status] ?? "membersMembershipStatusActive")}
                </Badge>
              </li>
            ))}
            {membershipList.length === 0 && (
              <li className="py-2.5 text-sm text-muted-foreground">{t("membersNoMemberships")}</li>
            )}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("membersInvoicesTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          {printError && <p className="mb-2 text-sm text-destructive">{printError}</p>}
          <ul className="divide-y">
            {invoiceList.map((inv) => {
              const pendingNotes = creditNoteList.filter(
                (cn) => cn.invoice === inv.id && !cn.approved_by
              );
              const panelOpen = openPanel?.invoiceId === inv.id ? openPanel.kind : null;

              return (
                <li key={inv.id} className="py-3">
                  <div className="flex items-center justify-between">
                    <span className="font-dashboard-mono text-xs text-muted-foreground">
                      {inv.number}
                    </span>
                    <span className="font-dashboard-mono text-sm font-medium">
                      {formatNpr(inv.total_npr, { symbol: true })}{" "}
                      <span className="font-sans font-normal text-muted-foreground">
                        ({t(INVOICE_STATUS_KEY[inv.status] ?? "membersInvoiceStatusDraft")})
                      </span>
                    </span>
                  </div>

                  <div className="mt-2 flex flex-wrap items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs text-muted-foreground hover:text-foreground"
                      onClick={() => openPdf(inv.id)}
                    >
                      <FileText size={13} strokeWidth={2} data-icon="inline-start" />
                      {t("membersPdfAction")}
                    </Button>
                    {bridgeReady && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs text-muted-foreground hover:text-foreground"
                        disabled={printingId === inv.id}
                        onClick={() => printToThermalPrinter(inv)}
                      >
                        <Printer size={13} strokeWidth={2} data-icon="inline-start" />
                        {printingId === inv.id ? t("membersPrinting") : t("membersPrintAction")}
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs text-muted-foreground hover:text-foreground"
                      onClick={() => sendReceiptSms(inv.id)}
                    >
                      <MessageSquareText size={13} strokeWidth={2} data-icon="inline-start" />
                      {t("membersSmsReceiptAction")}
                    </Button>
                    {inv.status === "draft" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs text-primary hover:text-primary"
                        onClick={() => setOpenPanel({ invoiceId: inv.id, kind: "pay" })}
                      >
                        <Wallet size={13} strokeWidth={2} data-icon="inline-start" />
                        {t("membersCollectPaymentAction")}
                      </Button>
                    )}
                    {inv.status === "issued" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs text-primary hover:text-primary"
                        onClick={() => setOpenPanel({ invoiceId: inv.id, kind: "cn" })}
                      >
                        <Receipt size={13} strokeWidth={2} data-icon="inline-start" />
                        {t("membersRequestCreditNoteAction")}
                      </Button>
                    )}
                    {isOwner && inv.status !== "void" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs text-destructive hover:text-destructive"
                        onClick={() => setOpenPanel({ invoiceId: inv.id, kind: "void" })}
                      >
                        <X size={13} strokeWidth={2} data-icon="inline-start" />
                        {t("membersVoidAction")}
                      </Button>
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
                            {formatNpr(cn.amount_npr, { symbol: true })} - {cn.reason}
                          </span>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 px-2 text-xs text-accent hover:text-accent"
                            onClick={async () => {
                              await approveCreditNote(cn.id);
                              invalidateInvoices();
                            }}
                          >
                            <Check size={12} strokeWidth={2} data-icon="inline-start" />
                            {t("membersApproveAction")}
                          </Button>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
            {invoiceList.length === 0 && (
              <li className="py-2.5 text-sm text-muted-foreground">{t("membersNoInvoices")}</li>
            )}
          </ul>
        </CardContent>
      </Card>
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
  const t = useTranslations("admin");
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
      setError(t("membersPaymentRecordError"));
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-2 flex flex-wrap items-end gap-2 border-t pt-2.5">
      {error && <p className="w-full text-xs text-destructive">{error}</p>}
      <Select value={mode} onValueChange={(v) => setMode(v as PaymentMode)}>
        <SelectTrigger className="h-8 w-36 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {DESK_PAYMENT_MODES.map((m) => (
            <SelectItem key={m.value} value={m.value}>
              {t(m.labelKey)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Input
        type="number"
        step="0.01"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        className="h-8 w-28 text-xs"
        required
      />
      <Button type="submit" size="sm" disabled={submitting}>
        {submitting ? "..." : t("membersConfirmAction")}
      </Button>
      <Button type="button" variant="ghost" size="sm" className="text-muted-foreground" onClick={onCancel}>
        {t("membersCancelAction")}
      </Button>
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
  const t = useTranslations("admin");
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
      setError(t("membersVoidError"));
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-2 flex flex-wrap items-end gap-2 border-t pt-2.5">
      {error && <p className="w-full text-xs text-destructive">{error}</p>}
      <Input
        placeholder={t("membersVoidReasonPlaceholder")}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        className="h-8 flex-1 text-xs"
        required
      />
      <Button type="submit" size="sm" variant="destructive" disabled={submitting}>
        {submitting ? "..." : t("membersVoidAction")}
      </Button>
      <Button type="button" variant="ghost" size="sm" className="text-muted-foreground" onClick={onCancel}>
        {t("membersCancelAction")}
      </Button>
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
  const t = useTranslations("admin");
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
      setError(t("membersCreditNoteError"));
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-2 flex flex-wrap items-end gap-2 border-t pt-2.5">
      {error && <p className="w-full text-xs text-destructive">{error}</p>}
      <Input
        type="number"
        step="0.01"
        placeholder={t("membersAmountPlaceholder")}
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        className="h-8 w-28 text-xs"
        required
      />
      <Input
        placeholder={t("membersReasonPlaceholder")}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        className="h-8 flex-1 text-xs"
        required
      />
      <Button type="submit" size="sm" disabled={submitting}>
        {submitting ? "..." : t("membersSubmitForApprovalAction")}
      </Button>
      <Button type="button" variant="ghost" size="sm" className="text-muted-foreground" onClick={onCancel}>
        {t("membersCancelAction")}
      </Button>
    </form>
  );
}
