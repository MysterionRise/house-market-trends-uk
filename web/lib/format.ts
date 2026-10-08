/** Indicator values in words and units a reader can take in at a glance. */
export function formatValue(value: number | null | undefined, unit: string): string {
  if (value == null || Number.isNaN(value)) return "–";
  if (unit.startsWith("£")) return `£${Math.round(value).toLocaleString("en-GB")}`;
  if (unit === "metres") return value >= 1000 ? `${(value / 1000).toFixed(1)} km` : `${Math.round(value)} m`;
  if (unit.startsWith("%")) return `${value.toFixed(value > 0 && value < 10 ? 1 : 0)}%`;
  // A share of residents (IoD rates are 0–1)
  if (unit === "rate") return `${Math.round(value * 100)}%`;
  // Access and quality indices run 0–1 (1 = what a typical suburb has); out of 10 reads
  // better than a decimal and can't be mistaken for a 0–100 score
  if (/^(index|quality|rating) 0–1/.test(unit)) return `${(value * 10).toFixed(1).replace(/\.0$/, "")}/10`;
  if (Math.abs(value) >= 100) return Math.round(value).toLocaleString("en-GB");
  return value.toFixed(1);
}
