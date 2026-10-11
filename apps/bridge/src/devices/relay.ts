import { ZkSidecarClient } from "./zk-sidecar-client.js";

/** Triggers the gate's turnstile relay for `durationMs`, then releases it.
 * Two relay styles are common in the field:
 *  - A ZK access-controller's own aux output, driven through the sidecar
 *    (not yet a pyzk primitive -- ships as a no-op until a device with this
 *    output is on hand to test against; see the ceiling note below).
 *  - A standalone USB relay board, driven directly over serial.
 * `trigger()` picks whichever `driver` the install's config names. */
export type RelayDriver =
  | { kind: "zk-aux-output"; client: ZkSidecarClient }
  | { kind: "usb-serial"; write: (bytes: Buffer) => void };

export async function triggerRelay(driver: RelayDriver, durationMs = 3000): Promise<void> {
  if (driver.kind === "usb-serial") {
    driver.write(Buffer.from([0x01])); // open
    await new Promise((resolve) => setTimeout(resolve, durationMs));
    driver.write(Buffer.from([0x00])); // close
    return;
  }

  // ponytail: pyzk has no documented aux-relay-output call, and the
  // sidecar protocol doesn't expose one yet -- wire it up once a real
  // ZK access controller with a relay output is available to test
  // against, rather than guessing at an untested command here.
  throw new Error("zk-aux-output relay driver is not implemented yet -- use usb-serial");
}

/** Opens a USB relay board on `portPath` (e.g. "COM3" on Windows,
 * "/dev/ttyUSB0" on a Pi) as a usb-serial RelayDriver. Dynamic import of
 * `serialport`, same reasoning as secure-store.ts's dynamic `keytar`
 * import -- a missing/unsupported serial adapter on a given install
 * shouldn't crash the whole bridge process at startup, only the relay
 * feature on that install. */
export async function openSerialRelayDriver(portPath: string): Promise<RelayDriver> {
  const { SerialPort } = await import("serialport");
  const port = new SerialPort({ path: portPath, baudRate: 9600 });
  return {
    kind: "usb-serial",
    write: (bytes: Buffer) => {
      port.write(bytes);
    },
  };
}
