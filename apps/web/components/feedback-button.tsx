"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { createSupportTicket } from "@fitkhata/api-client";
import { MessageCircle } from "lucide-react";

import packageJson from "../package.json";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const APP_VERSION = packageJson.version;

/** H3's pilot-readiness ask: a feedback/bug-report button reachable from
 * anywhere in the admin console, filing straight into the SupportTicket
 * inbox platform staff already work from ((superadmin)/platform/tickets)
 * -- that endpoint and its api-client wrapper already existed with
 * nothing in the tenant-facing app ever calling them. Auto-attaches the
 * current URL + app version so platform staff don't have to ask for them.
 */
export function FeedbackButton() {
  const pathname = usePathname();
  const t = useTranslations("admin");
  const [open, setOpen] = useState(false);
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  function reset() {
    setSubject("");
    setMessage("");
    setError(null);
    setSent(false);
  }

  async function submit() {
    setError(null);
    setSubmitting(true);
    try {
      const context = `\n\n— sent from ${pathname} · FitKhata v${APP_VERSION}`;
      await createSupportTicket({
        subject,
        message: message ? `${message}${context}` : context.trim(),
      });
      setSent(true);
    } catch {
      setError(t("feedbackError"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={t("feedbackButtonLabel")}>
          <MessageCircle size={18} strokeWidth={2} />
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{sent ? t("feedbackThanks") : t("feedbackTitle")}</DialogTitle>
        </DialogHeader>

        {sent ? (
          <p className="text-sm text-muted-foreground">{t("feedbackThanksBody")}</p>
        ) : (
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="feedback-subject">{t("feedbackSubject")}</Label>
              <Input
                id="feedback-subject"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder={t("feedbackSubjectPlaceholder")}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="feedback-message">{t("feedbackDetails")}</Label>
              <Textarea
                id="feedback-message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={4}
                placeholder={t("feedbackDetailsPlaceholder")}
              />
            </div>
            <p className="text-xs text-muted-foreground">{t("feedbackAutoContext")}</p>
            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
        )}

        <DialogFooter>
          {sent ? (
            <Button onClick={() => setOpen(false)}>{t("feedbackClose")}</Button>
          ) : (
            <>
              <Button variant="outline" onClick={() => setOpen(false)}>
                {t("feedbackCancel")}
              </Button>
              <Button onClick={submit} disabled={!subject.trim() || submitting}>
                {submitting ? t("feedbackSending") : t("feedbackSend")}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
