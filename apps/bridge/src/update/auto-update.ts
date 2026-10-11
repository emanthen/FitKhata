import { createHash } from "node:crypto";
import { readFileSync, renameSync, writeFileSync } from "node:fs";

import { verifyAsync } from "@noble/ed25519";

export interface GitHubRelease {
  tag_name: string;
  assets: { name: string; browser_download_url: string }[];
}

export interface UpdateConfig {
  repo: string; // "owner/name"
  currentVersion: string;
  publicKeyHex: string; // Ed25519 public key for this project's release signing key
  installPath: string; // path to the running binary/bundle to replace
}

/** Each release publishes <asset>, <asset>.sha256, and <asset>.sha256.sig
 * (the sha256 file's bytes, Ed25519-signed with the project's release key)
 * -- a plain checksum file plus one signature, not a GPG keyring, so there's
 * no GPG binary dependency on the end-user's Windows PC or Pi. */
export async function checkForUpdate(config: UpdateConfig): Promise<GitHubRelease | null> {
  const res = await fetch(`https://api.github.com/repos/${config.repo}/releases/latest`, {
    headers: { accept: "application/vnd.github+json" },
  });
  if (!res.ok) throw new Error(`GitHub releases check failed: ${res.status}`);
  const release = (await res.json()) as GitHubRelease;

  if (release.tag_name === config.currentVersion) return null;
  return release;
}

async function fetchBuffer(url: string): Promise<Buffer> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`download failed: ${url} (${res.status})`);
  return Buffer.from(await res.arrayBuffer());
}

function assetUrl(release: GitHubRelease, suffix: string): string {
  const asset = release.assets.find((a) => a.name.endsWith(suffix));
  if (!asset) throw new Error(`release ${release.tag_name} is missing a *${suffix} asset`);
  return asset.browser_download_url;
}

/** Downloads the new binary + its signed checksum, verifies the signature
 * BEFORE touching anything on disk, verifies the checksum matches the
 * downloaded bytes, then atomically swaps it in. Throws (never partially
 * installs) if either check fails. Caller is responsible for restarting
 * the service afterward (node-windows / systemd). */
export async function downloadAndVerify(
  config: UpdateConfig,
  release: GitHubRelease,
  assetSuffix: string
): Promise<void> {
  const binaryUrl = assetUrl(release, assetSuffix);
  const checksumUrl = assetUrl(release, `${assetSuffix}.sha256`);
  const signatureUrl = assetUrl(release, `${assetSuffix}.sha256.sig`);

  const [binary, checksumFile, signature] = await Promise.all([
    fetchBuffer(binaryUrl),
    fetchBuffer(checksumUrl),
    fetchBuffer(signatureUrl),
  ]);

  const publicKey = Buffer.from(config.publicKeyHex, "hex");
  const signatureValid = await verifyAsync(signature, checksumFile, publicKey);
  if (!signatureValid) {
    throw new Error("release checksum signature is invalid -- refusing to install");
  }

  const expectedHash = checksumFile.toString("utf8").trim().split(/\s+/)[0];
  const actualHash = createHash("sha256").update(binary).digest("hex");
  if (actualHash !== expectedHash) {
    throw new Error("downloaded binary does not match its signed checksum -- refusing to install");
  }

  const tmpPath = `${config.installPath}.download`;
  writeFileSync(tmpPath, binary, { mode: 0o755 });
  renameSync(tmpPath, config.installPath);
}

export function readInstalledVersion(versionFilePath: string): string {
  return readFileSync(versionFilePath, "utf8").trim();
}
