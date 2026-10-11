// H2 scenario 1: gate batch sync -- 2,000 gyms x 50 scans/min.
//
// Models what apps/bridge and the gate kiosk PWA actually do: buffer scans
// locally, then flush a batch every few seconds (apps/bridge's own
// sync-loop.ts defaults to a 10s flush interval). 50 scans/min per gym at
// a 10s flush interval is ~8 checkins per batch, so this runs 2,000
// virtual devices each POSTing an 8-row batch roughly every 10s, rather
// than firing 2,000*50=100,000 individual single-row requests/min (that
// would test a traffic shape this system never actually produces).
//
// Needs a real device token per virtual gym -- there is no way to load-
// test gate/checkins:batch without one, since IsGateDevice checks a real
// GateDevice row. Seed 2,000 paired devices on the target first (or reuse
// however many you actually have and accept a smaller N), then provide
// their raw tokens as a JSON array via DEVICE_TOKENS_FILE.
//
// Run: k6 run -e BASE_URL=https://staging-api... -e DEVICE_TOKENS_FILE=./data/device-tokens.json tests/load/gate-batch-sync.js

import http from "k6/http";
import { check, sleep } from "k6";
import { SharedArray } from "k6/data";
import { BASE_URL } from "./lib/config.js";

const deviceTokens = new SharedArray("device tokens", function () {
  const path = __ENV.DEVICE_TOKENS_FILE || "./data/device-tokens.json";
  try {
    return JSON.parse(open(path));
  } catch {
    // Local smoke-test fallback -- NOT a real load test, just proves the
    // script itself runs. Replace with a real seeded token to mean anything.
    return ["REPLACE_WITH_A_REAL_PAIRED_DEVICE_TOKEN"];
  }
});

const BATCH_SIZE = 8; // ~50 scans/min at a 10s flush interval
const FLUSH_INTERVAL_S = 10;

export const options = {
  scenarios: {
    gate_sync: {
      executor: "per-vu-iterations",
      vus: deviceTokens.length,
      iterations: 6, // 6 flushes = 1 minute of simulated traffic per VU
      maxDuration: "2m",
    },
  },
  thresholds: {
    // Writes -- H2's target.
    http_req_duration: ["p(95)<600"],
    checks: ["rate>0.99"],
  },
};

function randomMemberCode(gymIndex) {
  return `GYM${gymIndex}-${String(Math.floor(Math.random() * 9999)).padStart(4, "0")}`;
}

// Not cryptographically random -- just unique enough for a load test's
// client_uuid. Avoids depending on a specific k6 version's crypto module
// (k6's Web Crypto support is still experimental/version-dependent).
function fakeUuid() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export default function () {
  const token = deviceTokens[__VU % deviceTokens.length];
  const now = Date.now();

  const checkins = Array.from({ length: BATCH_SIZE }, (_, i) => ({
    client_uuid: fakeUuid(),
    member_code: randomMemberCode(__VU),
    check_in_at: new Date(now - i * 1000).toISOString(),
    source: "qr_gate",
  }));

  const res = http.post(
    `${BASE_URL}/api/v1/gate/checkins:batch`,
    JSON.stringify({ checkins }),
    { headers: { "content-type": "application/json", authorization: `Device ${token}` } }
  );

  check(res, {
    "status is 200": (r) => r.status === 200,
    // Most member_codes above are fabricated and won't resolve -- the
    // endpoint still returns 200 with those rows in `rejected`. The
    // meaningful check under load is that the server answered promptly,
    // not that every row matched a real member.
  });

  sleep(FLUSH_INTERVAL_S);
}
