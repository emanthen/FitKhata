# FitKhata Hardware Bridge

Runs on a Windows PC or Raspberry Pi at the gym, handling ZKTeco biometric
devices, turnstile relays, and ESC/POS receipt printers — optional add-ons
on top of the basic QR-scan gate (see `docs/onboarding/gate-tablet-setup.en.md`),
not required for a gym that's just using the tablet scanner.

## Install

```bash
pnpm install
pnpm build
```

Set the sidecar up (ZKTeco integration only — skip if you're not using a
biometric device):

```bash
cd sidecar && ./build.sh
```

## Configure

Environment variables (see `src/config.ts` for the full list and defaults):

| Variable | Required | Purpose |
|---|---|---|
| `FITKHATA_API_BASE_URL` | yes | Your gym's API, e.g. `https://api.fitkhata.com/api/v1` |
| `FITKHATA_WEB_ORIGIN` | yes | Your gym's web app origin — the only origin the local print endpoint will accept requests from |
| `FITKHATA_ZK_HOST` / `FITKHATA_ZK_PORT` | only for biometric | The ZKTeco device's LAN IP |
| `FITKHATA_RELAY_SERIAL_PORT` | only for a turnstile relay | e.g. `COM3` (Windows) or `/dev/ttyUSB0` (Pi) |
| `FITKHATA_PRINT_PORT` | no (default 7777) | Local print endpoint port |

## Pair with your gym

Same pairing code flow as the gate tablet — generate one from
**Settings → Gate kiosk** in the web app, then:

```bash
node dist/index.js --pair <code> "Front desk bridge"
```

This prints a **print-endpoint token** once to the console — copy it into
**Settings → Receipt printer** in the web app (that's a separate, local
secret from the device pairing token; it's what lets the web app's browser
talk to this machine's local print endpoint).

## Run it

```bash
node dist/index.js
```

Or install as a persistent service:

```bash
node dist/index.js --install-service   # Windows: node-windows: systemd on Linux
```

## What it does once running

- Polls `/gate/snapshot` for member status changes and pushes
  enrol/delete/disable to the ZKTeco device accordingly.
- Polls the ZKTeco device for new attendance logs, buffers them locally
  (survives a network outage with zero duplicate check-ins once back
  online), and syncs to `/gate/checkins:batch`.
- Fires the turnstile relay (if configured) on a locally-validated allow
  result — the same "never wait on the network to open the gate"
  principle the tablet kiosk follows.
- Serves `127.0.0.1:<port>/print` for the web app to send receipts to
  the thermal printer, rejecting anything not from your configured web
  origin with the right token.
- Heartbeats to `/gate/heartbeat` every 60s — an owner gets an SMS if this
  stops for more than 10 minutes.

## Tests

```bash
pnpm test
```
