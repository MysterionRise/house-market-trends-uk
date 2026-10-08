/**
 * Where the Python API and the data files live. In docker compose both are on the page's
 * own origin (an empty API URL and /data, through the proxy); `npm run dev` uses the
 * API's dev server, which also serves the data files.
 */
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
/** Tiles, scores.parquet and manifest.json */
export const DATA_URL = process.env.NEXT_PUBLIC_DATA_URL ?? `${API_URL}/data`;

/** DATA_URL as an absolute URL, for the PMTiles protocol (relative means this origin). */
export function absoluteDataUrl(): string {
  return new URL(DATA_URL, window.location.href).href.replace(/\/$/, "");
}
