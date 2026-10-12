"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createApiKey,
  listApiKeys,
  revokeApiKey,
  type ApiKeyScope,
  type ApiKeyWithSecret,
} from "@fitkhata/api-client";
import { KeyRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const SCOPES: { value: ApiKeyScope; labelKey: string }[] = [
  { value: "members:read", labelKey: "notifApiKeyScopeMembersRead" },
  { value: "memberships:read", labelKey: "notifApiKeyScopeMembershipsRead" },
  { value: "invoices:read", labelKey: "notifApiKeyScopeInvoicesRead" },
];

export default function ApiKeysSettingsPage() {
  const t = useTranslations("admin");
  const queryClient = useQueryClient();
  const apiKeys = useQuery({ queryKey: ["api-keys"], queryFn: listApiKeys, retry: false });

  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<ApiKeyScope[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [justCreated, setJustCreated] = useState<ApiKeyWithSecret | null>(null);

  const planGated = (apiKeys.error as { response?: { status?: number } } | undefined)?.response
    ?.status === 403;

  function toggleScope(scope: ApiKeyScope, checked: boolean) {
    setScopes((prev) => (checked ? [...prev, scope] : prev.filter((s) => s !== scope)));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (scopes.length === 0) {
      setError(t("notifApiKeyPickScopeError"));
      return;
    }
    setSubmitting(true);
    try {
      const created = await createApiKey({ name, scopes });
      setJustCreated(created);
      setName("");
      setScopes([]);
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    } catch {
      setError(t("notifApiKeyCreateError"));
    } finally {
      setSubmitting(false);
    }
  }

  async function revoke(id: string) {
    await revokeApiKey(id);
    queryClient.invalidateQueries({ queryKey: ["api-keys"] });
  }

  if (planGated) {
    return (
      <div className="max-w-2xl space-y-4">
        <h1 className="text-xl font-semibold tracking-tight">{t("settingsApiKeys")}</h1>
        <p className="text-sm text-muted-foreground">{t("notifApiKeyPlanGated")}</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">{t("settingsApiKeys")}</h1>

      {justCreated && (
        <Card className="border-primary/40 bg-primary/5">
          <CardContent className="space-y-1.5">
            <p className="text-sm font-medium">{t("notifApiKeyCopyNow")}</p>
            <code className="block overflow-x-auto rounded-md bg-background px-2.5 py-2 font-dashboard-mono text-sm">
              {justCreated.key}
            </code>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <KeyRound size={16} strokeWidth={2} className="text-primary" />
            {t("notifApiKeyActiveKeys")}
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            {t("notifApiKeyScopedCreds")}{" "}
            <code className="font-dashboard-mono">/api/public/v1/</code>.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <ul className="divide-y">
            {apiKeys.data
              ?.filter((k) => !k.revoked_at)
              .map((k) => (
                <li key={k.id} className="flex items-center justify-between py-2 text-sm">
                  <span>
                    {k.name}{" "}
                    <code className="font-dashboard-mono text-muted-foreground">
                      {k.key_prefix}...
                    </code>
                    <br />
                    <span className="text-xs text-muted-foreground">
                      {k.scopes.join(", ")}
                      {k.last_used_at
                        ? ` · ${t("settingsLastUsed", { date: new Date(k.last_used_at).toLocaleString() })}`
                        : ` · ${t("notifApiKeyNeverUsed")}`}
                    </span>
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    onClick={() => revoke(k.id)}
                  >
                    {t("settingsRevoke")}
                  </Button>
                </li>
              ))}
            {apiKeys.data?.filter((k) => !k.revoked_at).length === 0 && (
              <li className="py-2 text-sm text-muted-foreground">{t("notifApiKeyNoneYet")}</li>
            )}
          </ul>

          {error && <p className="text-sm text-destructive">{error}</p>}
          <form onSubmit={submit} className="space-y-3 border-t pt-3">
            <div className="space-y-1.5">
              <Label htmlFor="key-name">{t("notifApiKeyNameLabel")}</Label>
              <Input
                id="key-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("notifApiKeyNamePlaceholder")}
                className="h-8 w-64"
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label>{t("notifApiKeyScopesLabel")}</Label>
              <div className="flex flex-wrap gap-4">
                {SCOPES.map((scope) => (
                  <label
                    key={scope.value}
                    className="flex items-center gap-2 text-sm font-normal"
                  >
                    <Checkbox
                      checked={scopes.includes(scope.value)}
                      onCheckedChange={(checked) => toggleScope(scope.value, checked === true)}
                    />
                    {t(scope.labelKey)}
                  </label>
                ))}
              </div>
            </div>
            <Button type="submit" size="sm" disabled={submitting}>
              {submitting ? "..." : t("notifApiKeyCreateButton")}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
