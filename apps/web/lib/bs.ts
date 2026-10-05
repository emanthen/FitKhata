/**
 * AD <-> BS (Bikram Sambat) conversion. Mirrors apps/api/core/domain/bs.py —
 * keep the table and anchor in sync; see that module's docstring for sourcing
 * and the far-future-years caveat.
 */

export const MIN_BS_YEAR = 2070;
export const MAX_BS_YEAR = 2100;

export const BS_MONTH_LENGTHS: Record<number, number[]> = {
  2070: [31, 31, 31, 32, 31, 31, 29, 30, 30, 29, 30, 30],
  2071: [31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30],
  2072: [31, 32, 31, 32, 31, 30, 30, 29, 30, 29, 30, 30],
  2073: [31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31],
  2074: [31, 31, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30],
  2075: [31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30],
  2076: [31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30],
  2077: [31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31],
  2078: [31, 31, 31, 32, 31, 31, 30, 29, 30, 29, 30, 30],
  2079: [31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30],
  2080: [31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 30],
  2081: [31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 29, 31],
  2082: [31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30],
  2083: [31, 31, 32, 31, 31, 31, 30, 29, 30, 29, 30, 30],
  2084: [31, 31, 32, 31, 31, 30, 30, 30, 29, 30, 30, 30],
  2085: [31, 32, 31, 32, 30, 31, 30, 30, 29, 30, 30, 30],
  2086: [30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 30, 30],
  2087: [31, 31, 32, 31, 31, 31, 30, 30, 29, 30, 30, 30],
  2088: [30, 31, 32, 32, 30, 31, 30, 30, 29, 30, 30, 30],
  2089: [30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 30, 30],
  2090: [30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 30, 30],
  2091: [31, 31, 32, 31, 31, 31, 30, 30, 29, 30, 30, 30],
  2092: [30, 31, 32, 32, 31, 30, 30, 30, 29, 30, 30, 30],
  2093: [30, 32, 31, 32, 31, 30, 30, 30, 29, 30, 30, 30],
  2094: [31, 31, 32, 31, 31, 30, 30, 30, 29, 30, 30, 30],
  2095: [31, 31, 32, 31, 31, 31, 30, 29, 30, 30, 30, 30],
  2096: [30, 31, 32, 32, 31, 30, 30, 29, 30, 29, 30, 30],
  2097: [31, 32, 31, 32, 31, 30, 30, 30, 29, 30, 30, 30],
  2098: [31, 31, 32, 31, 31, 31, 29, 30, 29, 30, 29, 31],
  2099: [31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31],
  2100: [31, 32, 31, 32, 31, 30, 30, 30, 29, 29, 30, 31],
};

// BS 2070-01-01 == AD 2013-04-14 (Nepali New Year), the anchor for this table.
const ANCHOR_BS_YEAR = 2070;
const ANCHOR_AD = Date.UTC(2013, 3, 14); // months are 0-indexed

export const MONTH_NAMES_EN = [
  "Baisakh", "Jestha", "Ashadh", "Shrawan", "Bhadra", "Ashwin",
  "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra",
];
export const MONTH_NAMES_NE = [
  "बैशाख", "जेठ", "असार", "श्रावण", "भदौ", "असोज",
  "कार्तिक", "मंसिर", "पुष", "माघ", "फागुन", "चैत",
];
const NE_DIGITS = ["०", "१", "२", "३", "४", "५", "६", "७", "८", "९"];

function toNeDigits(s: string): string {
  return s.replace(/[0-9]/g, (d) => NE_DIGITS[Number(d)]);
}

function yearLength(year: number): number {
  return BS_MONTH_LENGTHS[year].reduce((a, b) => a + b, 0);
}

const MS_PER_DAY = 24 * 60 * 60 * 1000;

export interface BsDate {
  year: number;
  month: number; // 1-12
  day: number;
}

export function toBs(adDate: Date): BsDate {
  const target = Date.UTC(adDate.getUTCFullYear(), adDate.getUTCMonth(), adDate.getUTCDate());
  let offset = Math.round((target - ANCHOR_AD) / MS_PER_DAY);
  if (offset < 0) {
    throw new RangeError(`date is before the BS lookup table starts`);
  }

  let year = ANCHOR_BS_YEAR;
  while (offset >= yearLength(year)) {
    offset -= yearLength(year);
    year += 1;
    if (year > MAX_BS_YEAR) {
      throw new RangeError(`date is beyond the BS lookup table (max BS ${MAX_BS_YEAR})`);
    }
  }

  const monthLengths = BS_MONTH_LENGTHS[year];
  let month = 1;
  for (const length of monthLengths) {
    if (offset < length) break;
    offset -= length;
    month += 1;
  }

  return { year, month, day: offset + 1 };
}

export function toAd(year: number, month: number, day: number): Date {
  if (year < MIN_BS_YEAR || year > MAX_BS_YEAR) {
    throw new RangeError(`BS year ${year} is outside the lookup table (${MIN_BS_YEAR}-${MAX_BS_YEAR})`);
  }
  if (month < 1 || month > 12) {
    throw new RangeError(`BS month ${month} out of range`);
  }
  const monthLengths = BS_MONTH_LENGTHS[year];
  if (day < 1 || day > monthLengths[month - 1]) {
    throw new RangeError(`BS day ${day} out of range for ${year}-${String(month).padStart(2, "0")}`);
  }

  let days = 0;
  for (let y = ANCHOR_BS_YEAR; y < year; y++) {
    days += yearLength(y);
  }
  days += monthLengths.slice(0, month - 1).reduce((a, b) => a + b, 0);
  days += day - 1;

  return new Date(ANCHOR_AD + days * MS_PER_DAY);
}

export function formatBs(adDate: Date, lang: "en" | "ne" = "en"): string {
  const { year, month, day } = toBs(adDate);
  if (lang === "ne") {
    return toNeDigits(`${year} ${MONTH_NAMES_NE[month - 1]} ${day}`);
  }
  return `${year} ${MONTH_NAMES_EN[month - 1]} ${day}`;
}
