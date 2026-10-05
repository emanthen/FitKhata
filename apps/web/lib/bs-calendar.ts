// NOT a duplicate of ./bs.ts — that module's hand-rolled table (mirrored by
// apps/api/core/domain/bs.py) only covers BS 2070-2100 (~AD 2013-2044),
// which is deliberately scoped to near-present operational dates (invoice/
// membership dates). A member's date of birth is routinely well outside
// that range (an adult member is typically born in the 1970s-2000s AD), so
// DOB conversion/display uses this separate, wider-range (BS 1975-2100)
// nepali-date-converter-backed utility instead. Everything else BS-related
// (fiscal year, any future membership/invoice BS display) should use
// ./bs.ts / core.domain.bs, not this file — don't reach for this one by
// default.
import NepaliDate from "nepali-date-converter";

// nepali-date-converter's toJsDate() returns a Date whose UTC wall-clock
// time is NOT midnight (it reflects NPT's +05:45 offset baked into UTC
// time-of-day), so reading its local-timezone getters only gives the right
// calendar day when the host's own TZ happens to be Asia/Kathmandu — not
// guaranteed on a server. Shifting by the same fixed offset and reading the
// UTC getters gives the correct AD date regardless of host timezone.
const NEPAL_UTC_OFFSET_MS = (5 * 60 + 45) * 60 * 1000;

export interface BsDate {
  year: number;
  month: number; // 1-indexed, unlike the underlying library
  day: number;
}

export function adToBs(ad: Date): BsDate {
  const nd = new NepaliDate(ad);
  return { year: nd.getYear(), month: nd.getMonth() + 1, day: nd.getDate() };
}

export function bsToAd(bs: BsDate): Date {
  const nd = new NepaliDate(bs.year, bs.month - 1, bs.day);
  const shifted = new Date(nd.toJsDate().getTime() + NEPAL_UTC_OFFSET_MS);
  return new Date(Date.UTC(shifted.getUTCFullYear(), shifted.getUTCMonth(), shifted.getUTCDate()));
}

export function formatBs(ad: Date): string {
  return new NepaliDate(ad).format("YYYY-MM-DD");
}

/** For an <input type="date">-style AD value (YYYY-MM-DD, no time/TZ). */
export function adIsoToBsLabel(adIso: string): string {
  const [y, m, d] = adIso.split("-").map(Number);
  return formatBs(new Date(Date.UTC(y, m - 1, d)));
}
