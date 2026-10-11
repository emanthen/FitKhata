"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useTranslations } from "next-intl";
import {
  createPairingCode,
  listSessions,
  revokeSession,
  type DeviceSession,
} from "@fitkhata/api-client";
import { Bell, ChevronRight, CreditCard, Laptop, Plug, Printer, QrCode, Ticket } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  clearBridgePrintConfig,
  getBridgePrintConfig,
  setBridgePrintConfig,
} from "@/lib/bridge-print";

function SettingsLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="flex items-center justify-between rounded-lg px-2.5 py-2 text-sm text-foreground/80 transition-colors hover:bg-muted hover:text-foreground"
    >
      {label}
      <ChevronRight size={15} strokeWidth={2} className="text-muted-foreground" />
    </Link>
  );
}

export default function SettingsPage() {
  const { gymId } = useParams<{ gymId: string }>();
  const t = useTranslations("admin");
  const [sessions, setSessions] = useState<DeviceSession[] | null>(null);

  function load() {
    listSessions().then(setSessions);
  }

  useEffect(() => {
    load();
  }, []);

  async function revoke(id: string) {
    await revokeSession(id);
    load();
  }

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">{t("settingsTitle")}</h1>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Ticket size={16} strokeWidth={2} className="text-primary" />
            {t("settingsMembership")}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col">
          <SettingsLink
            href={`/${gymId}/settings/plans`}
            label={t("settingsPlansAddons")}
          />
          <SettingsLink
            href={`/${gymId}/settings/promo-codes`}
            label={t("settingsPromoCodes")}
          />
          <SettingsLink
            href={`/${gymId}/members/import`}
            label={t("settingsImportMembers")}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CreditCard size={16} strokeWidth={2} className="text-primary" />
            {t("settingsBilling")}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col">
          <SettingsLink
            href={`/${gymId}/settings/payments`}
            label={t("settingsPaymentGateways")}
          />
          <SettingsLink href={`/${gymId}/billing/shift`} label={t("settingsCashShift")} />
          <SettingsLink
            href={`/${gymId}/billing/settlement`}
            label={t("settingsSettlementReport")}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell size={16} strokeWidth={2} className="text-primary" />
            {t("settingsNotifications")}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col">
          <SettingsLink
            href={`/${gymId}/settings/notifications/templates`}
            label={t("settingsTemplates")}
          />
          <SettingsLink
            href={`/${gymId}/settings/notifications/events`}
            label={t("settingsEventTriggers")}
          />
          <SettingsLink
            href={`/${gymId}/notifications/broadcast`}
            label={t("settingsBroadcast")}
          />
          <SettingsLink
            href={`/${gymId}/notifications/log`}
            label={t("settingsDeliveryLog")}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plug size={16} strokeWidth={2} className="text-primary" />
            {t("settingsIntegrations")}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col">
          <SettingsLink
            href={`/${gymId}/settings/api-keys`}
            label={t("settingsApiKeys")}
          />
          <SettingsLink href={`/${gymId}/settings/webhooks`} label={t("settingsWebhooks")} />
        </CardContent>
      </Card>

      <GateDeviceSection />
      <PrinterSettingsSection />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Laptop size={16} strokeWidth={2} className="text-primary" />
            {t("settingsDeviceSessions")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="divide-y">
            {sessions?.map((session) => (
              <li key={session.id} className="flex items-center justify-between py-2.5 text-sm">
                <span>
                  {session.user_agent || t("settingsUnknownDevice")} &middot;{" "}
                  {session.ip ?? t("settingsUnknownIp")}
                  <br />
                  <span className="text-xs text-muted-foreground">
                    {t("settingsLastUsed", {
                      date: new Date(session.last_used_at).toLocaleString(),
                    })}
                  </span>
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive hover:text-destructive"
                  onClick={() => revoke(session.id)}
                >
                  {t("settingsRevoke")}
                </Button>
              </li>
            ))}
            {sessions?.length === 0 && (
              <li className="py-2.5 text-sm text-muted-foreground">
                {t("settingsNoSessions")}
              </li>
            )}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

/** FR-3.x gate pairing: the backend endpoint and its api-client wrapper
 * (createPairingCode) already existed with nothing in the admin console
 * ever calling them -- a gym had no way to pair a kiosk at all without
 * someone hitting the API directly. Matches attendance.views
 * .GatePairingCodeView (manager+, 10-minute one-time code).
 */
function GateDeviceSection() {
  const t = useTranslations("admin");
  const [deviceName, setDeviceName] = useState("");
  const [code, setCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  async function generate() {
    setError(null);
    setGenerating(true);
    try {
      const result = await createPairingCode(deviceName.trim() || t("settingsKioskNamePlaceholder"));
      setCode(result.code);
    } catch {
      setError(t("settingsPairingCodeError"));
    } finally {
      setGenerating(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <QrCode size={16} strokeWidth={2} className="text-primary" />
          {t("settingsGateKiosk")}
        </CardTitle>
        <p className="text-sm text-muted-foreground">{t("settingsGateKioskBody")}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        {code ? (
          <div className="rounded-md border bg-muted/40 p-4 text-center">
            <p className="font-dashboard-mono text-3xl font-semibold tracking-widest">{code}</p>
            <p className="mt-1 text-xs text-muted-foreground">{t("settingsExpiresIn10")}</p>
            <Button
              variant="ghost"
              size="sm"
              className="mt-2"
              onClick={() => {
                setCode(null);
                setDeviceName("");
              }}
            >
              {t("settingsGenerateNewCode")}
            </Button>
          </div>
        ) : (
          <div className="flex flex-wrap items-end gap-2">
            <div className="space-y-1.5">
              <Label htmlFor="device-name">{t("settingsKioskName")}</Label>
              <Input
                id="device-name"
                value={deviceName}
                onChange={(e) => setDeviceName(e.target.value)}
                placeholder={t("settingsKioskNamePlaceholder")}
                className="h-8 w-48"
              />
            </div>
            <Button size="sm" onClick={generate} disabled={generating}>
              {generating ? "..." : t("settingsGeneratePairingCode")}
            </Button>
          </div>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </CardContent>
    </Card>
  );
}

/** Per-browser, not per-org: the receipt printer is wired to one specific
 * front-desk PC, which is where apps/bridge runs -- so the token it issued
 * at pairing time (printed once to the bridge's own console, see
 * apps/bridge/src/pairing.ts) is pasted here once, into THIS browser's
 * localStorage, not sent to or stored by the backend at all. */
function PrinterSettingsSection() {
  const t = useTranslations("admin");
  const [baseUrl, setBaseUrl] = useState("http://127.0.0.1:7777");
  const [token, setToken] = useState("");
  const [printerInterface, setPrinterInterface] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const existing = getBridgePrintConfig();
    if (existing) {
      setBaseUrl(existing.baseUrl);
      setToken(existing.token);
      setPrinterInterface(existing.printerInterface);
    }
  }, []);

  function save() {
    setBridgePrintConfig({ baseUrl, token, printerInterface });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  function clear() {
    clearBridgePrintConfig();
    setToken("");
    setPrinterInterface("");
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Printer size={16} strokeWidth={2} className="text-primary" />
          {t("settingsReceiptPrinter")}
        </CardTitle>
        <p className="text-sm text-muted-foreground">{t("settingsReceiptPrinterBody")}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-end gap-2">
          <div className="space-y-1.5">
            <Label htmlFor="bridge-url">{t("settingsBridgeUrl")}</Label>
            <Input
              id="bridge-url"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              className="h-8 w-56"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="bridge-token">{t("settingsPrintToken")}</Label>
            <Input
              id="bridge-token"
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="h-8 w-64"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="printer-interface">{t("settingsPrinterInterface")}</Label>
            <Input
              id="printer-interface"
              value={printerInterface}
              onChange={(e) => setPrinterInterface(e.target.value)}
              placeholder="tcp://192.168.1.50"
              className="h-8 w-48"
            />
          </div>
          <Button size="sm" onClick={save} disabled={!token || !printerInterface}>
            {saved ? t("settingsSaved") : t("settingsSave")}
          </Button>
          {token && (
            <Button variant="ghost" size="sm" onClick={clear} className="text-destructive">
              {t("settingsRemove")}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
