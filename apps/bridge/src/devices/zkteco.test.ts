import { PassThrough } from "node:stream";
import { createInterface } from "node:readline";

import { describe, expect, it } from "vitest";

import type { PendingCheckin } from "../types.js";
import { ZkSidecarClient } from "./zk-sidecar-client.js";
import {
  enrollMember,
  pollAttendanceOnce,
  removeMember,
  setMemberEnabled,
  syncEnrollment,
} from "./zkteco.js";

/** Fake ZK device: stands in for sidecar/zk_sidecar.py, speaking the exact
 * same JSON-lines protocol, driven by canned attendance logs and recording
 * every enrolment command it receives -- the "fake ZK device" the plan's
 * tests ask for, without needing a real device or a Python process. */
class FakeZkDevice {
  readonly toDevice = new PassThrough(); // parent writes here (this.io.stdin)
  readonly fromDevice = new PassThrough(); // parent reads here (this.io.stdout)
  readonly setUserCalls: { user_id: string; name: string }[] = [];
  readonly deleteUserCalls: string[] = [];
  private attendanceLog: { user_id: string; timestamp: string }[] = [];
  private failNextWith: string | undefined;

  constructor() {
    createInterface({ input: this.toDevice }).on("line", (line) => this._handle(line));
  }

  seedAttendance(rows: { user_id: string; timestamp: string }[]): void {
    this.attendanceLog = rows;
  }

  /** Makes the next command the device receives fail, simulating a
   * disconnected/unreachable device for one call. */
  failNextCommand(reason: string): void {
    this.failNextWith = reason;
  }

  private _reply(obj: Record<string, unknown>): void {
    this.fromDevice.write(JSON.stringify(obj) + "\n");
  }

  private _handle(line: string): void {
    if (this.failNextWith) {
      const reason = this.failNextWith;
      this.failNextWith = undefined;
      this._reply({ ok: false, error: reason });
      return;
    }
    const command = JSON.parse(line) as Record<string, unknown>;
    switch (command.cmd) {
      case "connect":
      case "ping":
        this._reply({ ok: true });
        return;
      case "poll_attendance": {
        const since = command.since_offset as number;
        this._reply({ ok: true, rows: this.attendanceLog.slice(since), next_offset: this.attendanceLog.length });
        return;
      }
      case "set_user":
        this.setUserCalls.push({ user_id: command.user_id as string, name: command.name as string });
        this._reply({ ok: true });
        return;
      case "delete_user":
        this.deleteUserCalls.push(command.user_id as string);
        this._reply({ ok: true });
        return;
      case "enable_user":
        this.setUserCalls.push({ user_id: command.user_id as string, name: command.user_id as string });
        this._reply({ ok: true });
        return;
      case "disable_user":
        this.deleteUserCalls.push(command.user_id as string);
        this._reply({ ok: true });
        return;
      default:
        this._reply({ ok: false, error: `unknown command: ${String(command.cmd)}` });
    }
  }
}

function clientFor(device: FakeZkDevice): ZkSidecarClient {
  return new ZkSidecarClient({ stdin: device.toDevice, stdout: device.fromDevice });
}

describe("ZkSidecarClient protocol framing", () => {
  it("connects and pings without error", async () => {
    const device = new FakeZkDevice();
    const client = clientFor(device);

    await expect(client.connect("10.0.0.5", 4370)).resolves.toBeUndefined();
    await expect(client.ping()).resolves.toBeUndefined();
  });

  it("rejects when the device reports an error", async () => {
    const device = new FakeZkDevice();
    const client = clientFor(device);

    device.failNextCommand("device unreachable");
    await expect(client.ping()).rejects.toThrow(/device unreachable/);
  });
});

describe("pollAttendanceOnce", () => {
  it("maps device user_id to member_code and emits one check-in per resolved row", async () => {
    const device = new FakeZkDevice();
    device.seedAttendance([
      { user_id: "1001", timestamp: "2026-10-11T06:00:00+00:00" },
      { user_id: "1002", timestamp: "2026-10-11T06:01:00+00:00" },
    ]);
    const client = clientFor(device);

    const memberCodes: Record<string, string> = { "1001": "GYM1-0042", "1002": "GYM1-0099" };
    const emitted: PendingCheckin[] = [];

    const nextOffset = await pollAttendanceOnce(
      client,
      0,
      (userId) => memberCodes[userId],
      (row) => emitted.push(row)
    );

    expect(nextOffset).toBe(2);
    expect(emitted).toHaveLength(2);
    expect(emitted[0]).toMatchObject({
      member_code: "GYM1-0042",
      check_in_at: "2026-10-11T06:00:00+00:00",
      source: "biometric",
    });
    expect(emitted[1]).toMatchObject({ member_code: "GYM1-0099" });
    // Every emitted row gets its own stable client_uuid.
    expect(emitted[0].client_uuid).not.toBe(emitted[1].client_uuid);
  });

  it("skips rows for device user_ids with no known member_code, without failing the poll", async () => {
    const device = new FakeZkDevice();
    device.seedAttendance([{ user_id: "9999", timestamp: "2026-10-11T06:00:00+00:00" }]);
    const client = clientFor(device);

    const emitted: PendingCheckin[] = [];
    const nextOffset = await pollAttendanceOnce(client, 0, () => undefined, (row) =>
      emitted.push(row)
    );

    expect(nextOffset).toBe(1);
    expect(emitted).toHaveLength(0);
  });

  it("only pulls rows after the given offset on a subsequent poll", async () => {
    const device = new FakeZkDevice();
    device.seedAttendance([{ user_id: "1001", timestamp: "2026-10-11T06:00:00+00:00" }]);
    const client = clientFor(device);

    const firstBatch: PendingCheckin[] = [];
    const offsetAfterFirst = await pollAttendanceOnce(
      client,
      0,
      () => "GYM1-0042",
      (row) => firstBatch.push(row)
    );
    expect(firstBatch).toHaveLength(1);

    device.seedAttendance([
      { user_id: "1001", timestamp: "2026-10-11T06:00:00+00:00" },
      { user_id: "1001", timestamp: "2026-10-11T06:05:00+00:00" },
    ]);
    const secondBatch: PendingCheckin[] = [];
    await pollAttendanceOnce(client, offsetAfterFirst, () => "GYM1-0042", (row) =>
      secondBatch.push(row)
    );

    expect(secondBatch).toHaveLength(1);
    expect(secondBatch[0].check_in_at).toBe("2026-10-11T06:05:00+00:00");
  });
});

describe("enrolment lifecycle", () => {
  it("pushes a new member to the device via set_user", async () => {
    const device = new FakeZkDevice();
    const client = clientFor(device);

    await enrollMember(client, "1003", "GYM1-0100");

    expect(device.setUserCalls).toEqual([{ user_id: "1003", name: "GYM1-0100" }]);
  });

  it("removes a cancelled member via delete_user", async () => {
    const device = new FakeZkDevice();
    const client = clientFor(device);

    await removeMember(client, "1003");

    expect(device.deleteUserCalls).toEqual(["1003"]);
  });

  it("disabling a member deletes the device-side user; enabling re-adds it", async () => {
    const device = new FakeZkDevice();
    const client = clientFor(device);

    await setMemberEnabled(client, "1003", false);
    expect(device.deleteUserCalls).toEqual(["1003"]);

    await setMemberEnabled(client, "1003", true);
    expect(device.setUserCalls).toEqual([{ user_id: "1003", name: "1003" }]);
  });
});

describe("syncEnrollment", () => {
  const baseMember = {
    member_id: 42,
    member_code: "GYM1-0042",
    expiry_date: "2026-12-01",
    updated_at: "2026-10-11T00:00:00Z",
  };

  it("enrols an active member", async () => {
    const device = new FakeZkDevice();
    const client = clientFor(device);

    await syncEnrollment(client, { ...baseMember, status: "active" });

    expect(device.setUserCalls).toEqual([{ user_id: "42", name: "GYM1-0042" }]);
  });

  it("enrols a trial member the same as active", async () => {
    const device = new FakeZkDevice();
    const client = clientFor(device);

    await syncEnrollment(client, { ...baseMember, status: "trial" });

    expect(device.setUserCalls).toEqual([{ user_id: "42", name: "GYM1-0042" }]);
  });

  it("deletes a cancelled member's device enrolment", async () => {
    const device = new FakeZkDevice();
    const client = clientFor(device);

    await syncEnrollment(client, { ...baseMember, status: "cancelled" });

    expect(device.deleteUserCalls).toEqual(["42"]);
    expect(device.setUserCalls).toEqual([]);
  });

  it("disables (deletes device-side) an expired member", async () => {
    const device = new FakeZkDevice();
    const client = clientFor(device);

    await syncEnrollment(client, { ...baseMember, status: "expired" });

    expect(device.deleteUserCalls).toEqual(["42"]);
  });

  it("disables a frozen member", async () => {
    const device = new FakeZkDevice();
    const client = clientFor(device);

    await syncEnrollment(client, { ...baseMember, status: "frozen" });

    expect(device.deleteUserCalls).toEqual(["42"]);
  });
});
