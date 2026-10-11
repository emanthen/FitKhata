import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

const SERVICE_NAME = "fitkhata-bridge";

export interface BridgeCredentials {
  deviceId: number;
  gymId: string;
  deviceToken: string;
  printToken: string;
}

const ACCOUNT = "device-credentials";

/** OS keychain first (Windows Credential Manager / macOS Keychain / Linux
 * libsecret via keytar); falls back to an AES-256-GCM-encrypted local file
 * when no keychain backend is available -- e.g. a headless Raspberry Pi
 * without libsecret installed. Either way the raw token never touches
 * plain-text disk. */
export class SecureStore {
  constructor(private readonly dataDir: string) {}

  async save(creds: BridgeCredentials): Promise<void> {
    const json = JSON.stringify(creds);
    try {
      const keytar = await this._keytar();
      await keytar.setPassword(SERVICE_NAME, ACCOUNT, json);
    } catch {
      this._saveToEncryptedFile(json);
    }
  }

  async load(): Promise<BridgeCredentials | null> {
    try {
      const keytar = await this._keytar();
      const json = await keytar.getPassword(SERVICE_NAME, ACCOUNT);
      if (json) return JSON.parse(json) as BridgeCredentials;
    } catch {
      // fall through to the file fallback
    }
    return this._loadFromEncryptedFile();
  }

  private async _keytar() {
    // Dynamic import: keytar's native module can fail to load on a
    // keychain-less headless Linux box, and that failure should trigger the
    // file fallback below, not crash the whole process at startup.
    return (await import("keytar")).default;
  }

  private _keyFilePath(): string {
    return join(this.dataDir, ".keyfile");
  }

  private _secretsFilePath(): string {
    return join(this.dataDir, "secrets.enc.json");
  }

  private _loadOrCreateKey(): Buffer {
    const keyPath = this._keyFilePath();
    if (!existsSync(dirname(keyPath))) mkdirSync(dirname(keyPath), { recursive: true });
    if (existsSync(keyPath)) return readFileSync(keyPath);

    const key = randomBytes(32);
    writeFileSync(keyPath, key, { mode: 0o600 });
    return key;
  }

  private _saveToEncryptedFile(plaintext: string): void {
    const key = this._loadOrCreateKey();
    const iv = randomBytes(12);
    const cipher = createCipheriv("aes-256-gcm", key, iv);
    const ciphertext = Buffer.concat([cipher.update(plaintext, "utf8"), cipher.final()]);
    const authTag = cipher.getAuthTag();

    writeFileSync(
      this._secretsFilePath(),
      JSON.stringify({
        iv: iv.toString("hex"),
        authTag: authTag.toString("hex"),
        ciphertext: ciphertext.toString("hex"),
      }),
      { mode: 0o600 }
    );
  }

  private _loadFromEncryptedFile(): BridgeCredentials | null {
    const path = this._secretsFilePath();
    if (!existsSync(path) || !existsSync(this._keyFilePath())) return null;

    const key = this._loadOrCreateKey();
    const { iv, authTag, ciphertext } = JSON.parse(readFileSync(path, "utf8")) as {
      iv: string;
      authTag: string;
      ciphertext: string;
    };

    const decipher = createDecipheriv("aes-256-gcm", key, Buffer.from(iv, "hex"));
    decipher.setAuthTag(Buffer.from(authTag, "hex"));
    const plaintext = Buffer.concat([
      decipher.update(Buffer.from(ciphertext, "hex")),
      decipher.final(),
    ]).toString("utf8");

    return JSON.parse(plaintext) as BridgeCredentials;
  }
}
