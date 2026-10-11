import { randomBytes } from "node:crypto";

import { pairDevice } from "./api-client.js";
import type { BridgeCredentials } from "./secure-store.js";
import { SecureStore } from "./secure-store.js";

/** Redeems a gym manager's one-time pairing code (generated via the same
 * GatePairingCodeView the gate-kiosk PWA already uses) against POST
 * /gate/pair, then persists the resulting device token plus a freshly
 * generated local print-endpoint token. The print token is printed once to
 * the console for the owner to copy into the web app's printer settings --
 * there's no backend field for it yet (out of this change's scope), so this
 * is the handoff point until that setting exists. */
export async function pairAndStore(
  apiBaseUrl: string,
  code: string,
  deviceName: string,
  store: SecureStore
): Promise<BridgeCredentials> {
  const { device_id, gym_id, token } = await pairDevice(apiBaseUrl, code, deviceName);
  const printToken = randomBytes(24).toString("base64url");

  const creds: BridgeCredentials = {
    deviceId: device_id,
    gymId: gym_id,
    deviceToken: token,
    printToken,
  };
  await store.save(creds);

  console.log(`Paired as device #${device_id} for gym ${gym_id}.`);
  console.log(`Print-endpoint token (enter this in the web app's printer settings): ${printToken}`);

  return creds;
}
