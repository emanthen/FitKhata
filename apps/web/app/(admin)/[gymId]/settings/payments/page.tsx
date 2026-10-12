"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createGatewayCredential,
  deleteGatewayCredential,
  getOrgSettings,
  listGatewayCredentials,
  testGatewayConnection,
  updateOrgSettings,
  type GatewayCredential,
  type GatewayEnvironment,
  type GatewayProvider,
} from "@fitkhata/api-client";
import { CreditCard, Percent, Trash2, Wifi } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const PROVIDERS: { value: GatewayProvider; label: string }[] = [
  { value: "esewa", label: "eSewa" },
  { value: "khalti", label: "Khalti" },
  { value: "fonepay", label: "Fonepay" },
];

export default function PaymentSettingsPage() {
  const t = useTranslations("admin");
  const queryClient = useQueryClient();
  const credentials = useQuery({
    queryKey: ["gateway-credentials"],
    queryFn: listGatewayCredentials,
  });

  const [provider, setProvider] = useState<GatewayProvider>("esewa");
  const [environment, setEnvironment] = useState<GatewayEnvironment>("sandbox");
  const [merchantCode, setMerchantCode] = useState("");
  const [secret, setSecret] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [hmacKey, setHmacKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [testResults, setTestResults] = useState<Record<string, string>>({});

  const list: GatewayCredential[] = Array.isArray(credentials.data)
    ? credentials.data
    : ((credentials.data as { results: GatewayCredential[] } | undefined)?.results ?? []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await createGatewayCredential({
        provider,
        environment,
        merchant_code: merchantCode,
        secret: provider === "fonepay" ? undefined : secret,
        username: provider === "fonepay" ? username : undefined,
        password: provider === "fonepay" ? password : undefined,
        hmac_key: provider === "fonepay" ? hmacKey : undefined,
      });
      setMerchantCode("");
      setSecret("");
      setUsername("");
      setPassword("");
      setHmacKey("");
      queryClient.invalidateQueries({ queryKey: ["gateway-credentials"] });
    } catch {
      setError(t("billingGatewayCredentialError"));
    } finally {
      setSubmitting(false);
    }
  }

  async function test(id: string) {
    setTestResults((prev) => ({ ...prev, [id]: t("billingGatewayTesting") }));
    try {
      const result = await testGatewayConnection(id);
      setTestResults((prev) => ({
        ...prev,
        [id]: result.ok
          ? t("billingGatewayReachable")
          : t("billingGatewayFailed", { detail: result.detail ?? t("billingGatewayUnknownError") }),
      }));
    } catch {
      setTestResults((prev) => ({ ...prev, [id]: t("billingGatewayFailedRequestError") }));
    }
  }

  async function remove(id: string) {
    await deleteGatewayCredential(id);
    queryClient.invalidateQueries({ queryKey: ["gateway-credentials"] });
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-xl font-semibold tracking-tight">{t("billingPaymentSettingsTitle")}</h1>

      <VatSettingsSection />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CreditCard size={16} strokeWidth={2} className="text-primary" />
            {t("billingGatewayCredentialsTitle")}
          </CardTitle>
          <p className="text-sm text-muted-foreground">{t("billingGatewayCredentialsBody")}</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <ul className="divide-y">
            {list.map((c) => (
              <li key={c.id} className="py-2.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="capitalize">
                    {c.provider} &middot; {c.environment}
                  </span>
                  <span className="text-muted-foreground">
                    {c.is_configured ? t("billingGatewayConfigured") : t("billingGatewayNotConfigured")}
                  </span>
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-muted-foreground hover:text-foreground"
                    onClick={() => test(c.id)}
                  >
                    <Wifi size={13} strokeWidth={2} data-icon="inline-start" />
                    {t("billingGatewayTestConnection")}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-destructive hover:text-destructive"
                    onClick={() => remove(c.id)}
                  >
                    <Trash2 size={13} strokeWidth={2} data-icon="inline-start" />
                    {t("settingsRemove")}
                  </Button>
                  {testResults[c.id] && (
                    <span className="text-xs text-muted-foreground">{testResults[c.id]}</span>
                  )}
                </div>
              </li>
            ))}
            {list.length === 0 && (
              <li className="py-2.5 text-sm text-muted-foreground">
                {t("billingGatewayNoneConfigured")}
              </li>
            )}
          </ul>

          {error && <p className="text-sm text-destructive">{error}</p>}
          <form onSubmit={submit} className="space-y-3 rounded-lg border p-3">
            <div className="flex flex-wrap gap-2">
              <div className="space-y-1.5">
                <Label htmlFor="provider">{t("billingGatewayProviderLabel")}</Label>
                <Select value={provider} onValueChange={(v) => setProvider(v as GatewayProvider)}>
                  <SelectTrigger id="provider" className="h-8 w-36 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PROVIDERS.map((p) => (
                      <SelectItem key={p.value} value={p.value}>
                        {p.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="environment">{t("billingGatewayEnvironmentLabel")}</Label>
                <Select
                  value={environment}
                  onValueChange={(v) => setEnvironment(v as GatewayEnvironment)}
                >
                  <SelectTrigger id="environment" className="h-8 w-32 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sandbox">{t("billingGatewaySandbox")}</SelectItem>
                    <SelectItem value="live">{t("billingGatewayLive")}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="merchant-code">{t("billingGatewayMerchantCodeLabel")}</Label>
                <Input
                  id="merchant-code"
                  value={merchantCode}
                  onChange={(e) => setMerchantCode(e.target.value)}
                  className="h-8 w-40"
                  required
                />
              </div>
            </div>

            {provider === "fonepay" ? (
              <div className="flex flex-wrap gap-2">
                <div className="space-y-1.5">
                  <Label htmlFor="username">{t("billingGatewayUsernameLabel")}</Label>
                  <Input
                    id="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="h-8 w-40"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="password">{t("billingGatewayPasswordLabel")}</Label>
                  <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="h-8 w-40"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="hmac-key">{t("billingGatewayHmacKeyLabel")}</Label>
                  <Input
                    id="hmac-key"
                    type="password"
                    value={hmacKey}
                    onChange={(e) => setHmacKey(e.target.value)}
                    className="h-8 w-40"
                  />
                </div>
              </div>
            ) : (
              <div className="space-y-1.5">
                <Label htmlFor="secret">{t("billingGatewaySecretKeyLabel")}</Label>
                <Input
                  id="secret"
                  type="password"
                  value={secret}
                  onChange={(e) => setSecret(e.target.value)}
                  className="h-8 w-80"
                />
              </div>
            )}

            <Button type="submit" disabled={submitting}>
              {submitting ? "..." : t("billingGatewayAddCredentialButton")}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function VatSettingsSection() {
  const t = useTranslations("admin");
  const queryClient = useQueryClient();
  const org = useQuery({ queryKey: ["organization-settings"], queryFn: getOrgSettings });
  const [saving, setSaving] = useState(false);

  async function toggle() {
    if (!org.data) return;
    setSaving(true);
    try {
      await updateOrgSettings({ vat_inclusive_pricing: !org.data.vat_inclusive_pricing });
      queryClient.invalidateQueries({ queryKey: ["organization-settings"] });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Percent size={16} strokeWidth={2} className="text-primary" />
          {t("billingVatTitle")}
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          {t("billingVatBody")}{" "}
          <strong className="text-foreground">
            {org.isLoading
              ? "..."
              : org.data?.vat_inclusive_pricing
                ? t("billingVatInclusive")
                : t("billingVatExclusive")}
          </strong>
        </p>
      </CardHeader>
      <CardContent>
        <Button variant="outline" size="sm" onClick={toggle} disabled={saving || org.isLoading}>
          {org.data?.vat_inclusive_pricing
            ? t("billingVatSwitchToExclusive")
            : t("billingVatSwitchToInclusive")}
        </Button>
      </CardContent>
    </Card>
  );
}
