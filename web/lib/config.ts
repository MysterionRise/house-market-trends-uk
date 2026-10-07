/** Where the Python API and the static data files live. */
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
/** Tiles, scores.parquet and manifest.json (served by the API in dev, Caddy in compose). */
export const DATA_URL = process.env.NEXT_PUBLIC_DATA_URL ?? `${API_URL}/data`;
