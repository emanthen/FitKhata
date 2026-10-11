import sharp from "sharp";
import { printer as ThermalPrinter, types as PrinterTypes } from "node-thermal-printer";

export interface PrinterConfig {
  interface: string; // e.g. "tcp://192.168.1.50" or "printer:USB001"
}

export interface ReceiptLine {
  label: string;
  value: string;
}

export interface ReceiptData {
  gymName: string;
  titleNe: string; // e.g. "रसिद" (receipt)
  lines: ReceiptLine[];
  totalNpr: string;
}

/** Renders a receipt's Devanagari text as a raster PNG rather than relying
 * on the printer's own font table -- most ESC/POS thermal printers sold in
 * Nepal have no Devanagari glyphs built in. Built from an SVG (not a
 * headless browser) so this has no extra runtime dependency beyond sharp,
 * which the monorepo already uses (apps/web). Font availability is the one
 * real caveat: the host OS needs a Devanagari-capable font installed for
 * librsvg (sharp's SVG backend) to shape the text correctly -- ship/require
 * Noto Sans Devanagari on the install image. */
export async function renderReceiptPng(data: ReceiptData, widthPx = 384): Promise<Buffer> {
  const lineHeight = 28;
  const headerHeight = 70;
  const footerHeight = 50;
  const height = headerHeight + data.lines.length * lineHeight + footerHeight;

  const escapeXml = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  const lineSvg = data.lines
    .map(
      (line, i) =>
        `<text x="8" y="${headerHeight + i * lineHeight + 18}" font-family="Noto Sans Devanagari, sans-serif" font-size="18">${escapeXml(line.label)}</text>` +
        `<text x="${widthPx - 8}" y="${headerHeight + i * lineHeight + 18}" font-family="Noto Sans Devanagari, sans-serif" font-size="18" text-anchor="end">${escapeXml(line.value)}</text>`
    )
    .join("");

  const svg = `
    <svg width="${widthPx}" height="${height}" xmlns="http://www.w3.org/2000/svg">
      <rect width="100%" height="100%" fill="white" />
      <text x="${widthPx / 2}" y="28" font-family="Noto Sans Devanagari, sans-serif" font-size="22" font-weight="bold" text-anchor="middle">${escapeXml(data.gymName)}</text>
      <text x="${widthPx / 2}" y="54" font-family="Noto Sans Devanagari, sans-serif" font-size="18" text-anchor="middle">${escapeXml(data.titleNe)}</text>
      ${lineSvg}
      <text x="${widthPx / 2}" y="${height - 16}" font-family="Noto Sans Devanagari, sans-serif" font-size="20" font-weight="bold" text-anchor="middle">${escapeXml(data.totalNpr)}</text>
    </svg>`;

  return sharp(Buffer.from(svg)).png().toBuffer();
}

export async function printReceipt(config: PrinterConfig, data: ReceiptData): Promise<void> {
  const png = await renderReceiptPng(data);
  const printer = new ThermalPrinter({ type: PrinterTypes.EPSON, interface: config.interface });
  await printer.printImageBuffer(png);
  printer.cut();
  await printer.execute();
}

export async function openCashDrawer(config: PrinterConfig): Promise<void> {
  const printer = new ThermalPrinter({ type: PrinterTypes.EPSON, interface: config.interface });
  printer.openCashDrawer();
  await printer.execute();
}
