/** Indicator values in words and units a reader can take in at a glance. */
export function formatValue(value: number | null | undefined, unit: string, locale = "en-GB"): string {
  if (value == null || Number.isNaN(value)) return "–";
  // Round as toFixed does (so the English output is unchanged), then group and punctuate
  // for the locale
  const n = (v: number, digits = 0) =>
    Number(v.toFixed(digits)).toLocaleString(locale, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  if (unit.startsWith("£")) return `£${n(Math.round(value))}`;
  if (unit === "metres") return value >= 1000 ? `${n(value / 1000, 1)} km` : `${n(Math.round(value))} m`;
  if (unit.startsWith("%")) return `${n(value, value > 0 && value < 10 ? 1 : 0)}%`;
  // A share of residents (IoD rates are 0–1)
  if (unit === "rate") return `${n(Math.round(value * 100))}%`;
  // Access and quality indices run 0–1 (1 = what a typical suburb has); out of 10 reads
  // better than a decimal and can't be mistaken for a 0–100 score
  if (/^(index|quality|rating) 0–1/.test(unit)) return `${(value * 10).toFixed(1).replace(/\.0$/, "")}/10`;
  if (Math.abs(value) >= 100) return n(Math.round(value));
  return n(value, 1);
}
