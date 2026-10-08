import { useTranslations } from "next-intl";

import { Card, Muted } from "@/components/ui";

export interface SqlData {
  columns: string[];
  rows: unknown[][];
  truncated: boolean;
}

const ATTRIBUTION =
  "Contains public sector information licensed under the Open Government Licence v3.0; " +
  "data derived from OpenStreetMap © OpenStreetMap contributors, ODbL. See ATTRIBUTION.md.";

function toCsv(data: SqlData): string {
  const cell = (v: unknown) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
  };
  return [data.columns.map(cell).join(","), ...data.rows.map((r) => r.map(cell).join(",")), "", `# ${ATTRIBUTION}`].join("\n");
}

export function SqlResult({ data, query }: { data: SqlData; query?: string }) {
  const t = useTranslations("Sql");
  const download = () => {
    const url = URL.createObjectURL(new Blob([toCsv(data)], { type: "text/csv" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "liveability-query.csv" });
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <Card testId="sql-result" title={t("title")} subtitle={`${t("rows", { count: data.rows.length })}${data.truncated ? ` ${t("truncated")}` : ""}`}>
      {query && <pre className="mb-2 overflow-x-auto rounded bg-[var(--hover)] p-2 text-[11px]">{query}</pre>}
      <div className="max-h-72 overflow-auto">
        <table className="w-full text-xs tabular-nums">
          <thead className="sticky top-0 bg-[var(--surface-1)]">
            <tr>{data.columns.map((c) => <th key={c} className="py-1 pr-3 text-left font-medium text-[var(--text-secondary)]">{c}</th>)}</tr>
          </thead>
          <tbody>
            {data.rows.slice(0, 200).map((r, i) => (
              <tr key={i} className="border-t border-[var(--border)]">
                {r.map((v, j) => <td key={j} className="py-0.5 pr-3">{typeof v === "number" ? Number(v.toFixed(3)) : String(v ?? "")}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <button className="btn" onClick={download}>{t("download")}</button>
        {data.rows.length > 200 && <span className="text-xs text-[var(--text-muted)]">{t("showing")}</span>}
      </div>
      <Muted>{ATTRIBUTION}</Muted>
    </Card>
  );
}
