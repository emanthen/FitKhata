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

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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
    <div className="max-w-2xl space-y-8">
      <h1 className="text-2xl font-semibold">Payment settings</h1>

      <VatSettingsSection />

      <section className="space-y-3">
        <h2 className="text-lg font-medium">Gateway credentials</h2>
        <p className="text-sm opacity-60">
          Each gym uses its own eSewa / Khalti / Fonepay merchant account — FitKhata never
          handles your money directly.
        </p>

        <ul className="space-y-2 text-sm">
          {list.map((c) => (
            <li key={c.id} className="rounded border px-3 py-2">
              <div className="flex items-center justify-between">
                <span className="capitalize">
                  {c.provider} · {c.environment}
                </span>
                <span className="opacity-60">
                  {c.is_configured ? "Configured" : "Not configured"}
                </span>
              </div>
              <div className="mt-1 flex items-center gap-3 text-xs">
                <button className="text-blue-600 hover:underline" onClick={() => test(c.id)}>
                  Test connection
                </button>
                <button className="text-red-600 hover:underline" onClick={() => remove(c.id)}>
                  Remove
                </button>
                {testResults[c.id] && <span className="opacity-70">{testResults[c.id]}</span>}
              </div>
            </li>
          ))}
          {list.length === 0 && <li className="text-sm opacity-60">No gateways configured yet.</li>}
        </ul>

        {error && <p className="text-sm text-red-600">{error}</p>}
        <form onSubmit={submit} className="space-y-2 rounded border p-3">
          <div className="flex flex-wrap gap-2">
            <div className="space-y-1">
              <Label htmlFor="provider">Provider</Label>
              <select
                id="provider"
                value={provider}
                onChange={(e) => setProvider(e.target.value as GatewayProvider)}
                className="h-8 rounded border px-2 text-sm"
              >
                {PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="environment">Environment</Label>
              <select
                id="environment"
                value={environment}
                onChange={(e) => setEnvironment(e.target.value as GatewayEnvironment)}
                className="h-8 rounded border px-2 text-sm"
              >
                <option value="sandbox">Sandbox</option>
                <option value="live">Live</option>
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="merchant-code">Merchant code</Label>
              <Input
                id="merchant-code"
                value={merchantCode}
                onChange={(e) => setMerchantCode(e.target.value)}
                className="w-40"
                required
              />
            </div>
          </div>

          {provider === "fonepay" ? (
            <div className="flex flex-wrap gap-2">
              <div className="space-y-1">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-40"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-40"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="hmac-key">HMAC key</Label>
                <Input
                  id="hmac-key"
                  type="password"
                  value={hmacKey}
                  onChange={(e) => setHmacKey(e.target.value)}
                  className="w-40"
                />
              </div>
            </div>
          ) : (
            <div className="space-y-1">
              <Label htmlFor="secret">Secret key</Label>
              <Input
                id="secret"
                type="password"
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                className="w-80"
              />
            </div>
          )}

          <Button type="submit" disabled={submitting}>
            {submitting ? "..." : "Add credential"}
          </Button>
        </form>
      </section>
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
    <section className="space-y-2">
      <h2 className="text-lg font-medium">VAT</h2>
      <p className="text-sm opacity-60">
        Whether your plan/item prices already include VAT (sticker price = final price), or VAT is
        added on top at invoice time. Currently:{" "}
        <strong>
          {org.isLoading ? "..." : org.data?.vat_inclusive_pricing ? "inclusive" : "exclusive"}
        </strong>
      </p>
      <Button variant="outline" size="sm" onClick={toggle} disabled={saving || org.isLoading}>
        {org.data?.vat_inclusive_pricing
          ? "Switch to VAT-exclusive pricing"
          : "Switch to VAT-inclusive pricing"}
      </Button>
    </section>
  );
}
