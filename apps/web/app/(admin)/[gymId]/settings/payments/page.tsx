"use client";

import { useState } from "react";
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
      setError("Couldn't save this credential — check the details.");
    } finally {
      setSubmitting(false);
    }
  }

  async function test(id: string) {
    setTestResults((prev) => ({ ...prev, [id]: "Testing..." }));
    try {
      const result = await testGatewayConnection(id);
      setTestResults((prev) => ({
        ...prev,
        [id]: result.ok ? "Reachable" : `Failed: ${result.detail ?? "unknown error"}`,
      }));
    } catch {
      setTestResults((prev) => ({ ...prev, [id]: "Failed: request error" }));
    }
  }

  async function remove(id: string) {
    await deleteGatewayCredential(id);
    queryClient.invalidateQueries({ queryKey: ["gateway-credentials"] });
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-xl font-semibold tracking-tight">Payment settings</h1>

      <VatSettingsSection />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CreditCard size={16} strokeWidth={2} className="text-primary" />
            Gateway credentials
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Each gym uses its own eSewa / Khalti / Fonepay merchant account - FitKhata never
            handles your money directly.
          </p>
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
                    {c.is_configured ? "Configured" : "Not configured"}
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
                    Test connection
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-destructive hover:text-destructive"
                    onClick={() => remove(c.id)}
                  >
                    <Trash2 size={13} strokeWidth={2} data-icon="inline-start" />
                    Remove
                  </Button>
                  {testResults[c.id] && (
                    <span className="text-xs text-muted-foreground">{testResults[c.id]}</span>
                  )}
                </div>
              </li>
            ))}
            {list.length === 0 && (
              <li className="py-2.5 text-sm text-muted-foreground">No gateways configured yet.</li>
            )}
          </ul>

          {error && <p className="text-sm text-destructive">{error}</p>}
          <form onSubmit={submit} className="space-y-3 rounded-lg border p-3">
            <div className="flex flex-wrap gap-2">
              <div className="space-y-1.5">
                <Label htmlFor="provider">Provider</Label>
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
                <Label htmlFor="environment">Environment</Label>
                <Select
                  value={environment}
                  onValueChange={(v) => setEnvironment(v as GatewayEnvironment)}
                >
                  <SelectTrigger id="environment" className="h-8 w-32 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sandbox">Sandbox</SelectItem>
                    <SelectItem value="live">Live</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="merchant-code">Merchant code</Label>
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
                  <Label htmlFor="username">Username</Label>
                  <Input
                    id="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="h-8 w-40"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="h-8 w-40"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="hmac-key">HMAC key</Label>
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
                <Label htmlFor="secret">Secret key</Label>
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
              {submitting ? "..." : "Add credential"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function VatSettingsSection() {
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
          VAT
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          Whether your plan/item prices already include VAT (sticker price = final price), or VAT
          is added on top at invoice time. Currently:{" "}
          <strong className="text-foreground">
            {org.isLoading ? "..." : org.data?.vat_inclusive_pricing ? "inclusive" : "exclusive"}
          </strong>
        </p>
      </CardHeader>
      <CardContent>
        <Button variant="outline" size="sm" onClick={toggle} disabled={saving || org.isLoading}>
          {org.data?.vat_inclusive_pricing
            ? "Switch to VAT-exclusive pricing"
            : "Switch to VAT-inclusive pricing"}
        </Button>
      </CardContent>
    </Card>
  );
}
