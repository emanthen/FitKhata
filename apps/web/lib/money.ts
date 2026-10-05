/** NPR money formatting. Mirrors apps/api/core/domain/money.py — keep in sync. */

function groupLakh(digits: string): string {
  if (digits.length <= 3) return digits;
  const tail = digits.slice(-3);
  let head = digits.slice(0, -3);
  const groups: string[] = [];
  while (head.length > 2) {
    groups.unshift(head.slice(-2));
    head = head.slice(0, -2);
  }
  if (head) groups.unshift(head);
  return [...groups, tail].join(",");
}

/**
 * Format a number/string amount as NPR with lakh grouping and 2 decimals,
 * rounding half-up (same as Python's Decimal ROUND_HALF_UP).
 *
 * Works on the decimal string directly (never float math) so it matches the
 * API's Decimal-based money.py bit for bit — pass the API's string amount
 * rather than a parsed float where precision matters.
 *
 * formatNpr('1234567.5') === '12,34,567.50'
 */
export function formatNpr(amount: number | string, opts: { symbol?: boolean } = {}): string {
  const raw = typeof amount === "number" ? amount.toString() : amount.trim();
  const match = /^(-)?(\d+)(?:\.(\d*))?$/.exec(raw);
  if (!match) throw new RangeError(`formatNpr: invalid amount "${amount}"`);
  const [, signPart, intStr, fracStrRaw] = match;

  // Keep 2 decimal places plus one extra digit to decide half-up rounding.
  const fracStr = `${fracStrRaw ?? ""}000`.slice(0, 3);
  const roundDigit = Number(fracStr[2]);
  let cents = BigInt(intStr) * 100n + BigInt(fracStr.slice(0, 2));
  if (roundDigit >= 5) cents += 1n;

  const negative = signPart === "-" && cents !== 0n;
  const intPart = (cents / 100n).toString();
  const fracPart = (cents % 100n).toString().padStart(2, "0");
  const formatted = `${negative ? "-" : ""}${groupLakh(intPart)}.${fracPart}`;
  return opts.symbol ? `Rs. ${formatted}` : formatted;
}
