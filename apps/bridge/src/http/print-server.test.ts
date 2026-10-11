import { request } from "node:http";
import type { AddressInfo } from "node:net";

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createPrintServer, type PrintServerConfig } from "./print-server.js";

const CONFIG: PrintServerConfig = {
  webOrigin: "https://app.fitkhata.com",
  printToken: "device-secret-token",
};

let server: ReturnType<typeof createPrintServer>;
let port: number;
let onPrint: ReturnType<typeof vi.fn>;

beforeEach(async () => {
  onPrint = vi.fn().mockResolvedValue(undefined);
  server = createPrintServer(CONFIG, onPrint);
  await new Promise<void>((resolve) => server.listen(0, resolve));
  port = (server.address() as AddressInfo).port;
});

afterEach(async () => {
  await new Promise<void>((resolve) => server.close(() => resolve()));
});

function post(options: { origin?: string; authorization?: string; body?: object }): Promise<{
  status: number;
  headers: Record<string, string | string[] | undefined>;
}> {
  return new Promise((resolve, reject) => {
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (options.origin) headers.origin = options.origin;
    if (options.authorization) headers.authorization = options.authorization;

    const req = request(
      { host: "127.0.0.1", port, path: "/print", method: "POST", headers },
      (res) => {
        res.on("data", () => undefined);
        res.on("end", () => resolve({ status: res.statusCode ?? 0, headers: res.headers }));
      }
    );
    req.on("error", reject);
    req.end(JSON.stringify(options.body ?? {}));
  });
}

function preflight(options: { origin?: string }): Promise<{
  status: number;
  headers: Record<string, string | string[] | undefined>;
}> {
  return new Promise((resolve, reject) => {
    const headers: Record<string, string> = {
      "access-control-request-method": "POST",
      "access-control-request-headers": "content-type, authorization",
    };
    if (options.origin) headers.origin = options.origin;

    const req = request(
      { host: "127.0.0.1", port, path: "/print", method: "OPTIONS", headers },
      (res) => {
        res.on("data", () => undefined);
        res.on("end", () => resolve({ status: res.statusCode ?? 0, headers: res.headers }));
      }
    );
    req.on("error", reject);
    req.end();
  });
}

describe("print server origin + token auth", () => {
  it("rejects a request from a different origin, even with the right token", async () => {
    const { status } = await post({
      origin: "https://evil.example.com",
      authorization: `Bearer ${CONFIG.printToken}`,
    });

    expect(status).toBe(403);
    expect(onPrint).not.toHaveBeenCalled();
  });

  it("rejects a request with no origin header at all", async () => {
    const { status } = await post({ authorization: `Bearer ${CONFIG.printToken}` });

    expect(status).toBe(403);
    expect(onPrint).not.toHaveBeenCalled();
  });

  it("rejects the right origin with a missing token", async () => {
    const { status } = await post({ origin: CONFIG.webOrigin });

    expect(status).toBe(403);
    expect(onPrint).not.toHaveBeenCalled();
  });

  it("rejects the right origin with the wrong token", async () => {
    const { status } = await post({
      origin: CONFIG.webOrigin,
      authorization: "Bearer wrong-token",
    });

    expect(status).toBe(403);
    expect(onPrint).not.toHaveBeenCalled();
  });

  it("accepts the right origin with the right token", async () => {
    const { status } = await post({
      origin: CONFIG.webOrigin,
      authorization: `Bearer ${CONFIG.printToken}`,
      body: { template: "receipt", invoice_number: "2083-00001" },
    });

    expect(status).toBe(200);
    expect(onPrint).toHaveBeenCalledWith({ template: "receipt", invoice_number: "2083-00001" });
  });
});

describe("print server CORS preflight", () => {
  // A JSON POST with an Authorization header is a "non-simple" request --
  // any real browser sends this OPTIONS preflight first and never issues
  // the actual POST if it doesn't get an allowing response. A plain
  // node:http client (used by the tests above) skips this entirely, so
  // those tests alone can't catch a server that would silently never work
  // from an actual browser tab -- which is exactly what the first version
  // of this file did.
  it("allows a preflight from the configured web origin", async () => {
    const { status, headers } = await preflight({ origin: CONFIG.webOrigin });

    expect(status).toBe(204);
    expect(headers["access-control-allow-origin"]).toBe(CONFIG.webOrigin);
    expect(headers["access-control-allow-methods"]).toContain("POST");
  });

  it("rejects a preflight from a different origin", async () => {
    const { status, headers } = await preflight({ origin: "https://evil.example.com" });

    expect(status).toBe(403);
    expect(headers["access-control-allow-origin"]).toBeUndefined();
  });

  it("includes the CORS header on the real POST response so the browser can read it", async () => {
    const { headers } = await post({
      origin: CONFIG.webOrigin,
      authorization: `Bearer ${CONFIG.printToken}`,
    });

    expect(headers["access-control-allow-origin"]).toBe(CONFIG.webOrigin);
  });

  it("omits the CORS header on a wrong-origin response, so its body is unreadable to that page's JS", async () => {
    const { headers } = await post({
      origin: "https://evil.example.com",
      authorization: `Bearer ${CONFIG.printToken}`,
    });

    expect(headers["access-control-allow-origin"]).toBeUndefined();
  });
});
