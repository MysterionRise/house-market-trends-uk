import { Card, Muted, formatValue } from "@/components/ui";
import type { Comparison } from "@/lib/contracts.gen";

const UNITS: Record<string, string> = {
  house_price: "£", gp_distance: "metres", supermarket_distance: "metres",
  no2: "µg/m³", patients_per_gp: "patients", population_density: "per km²",
};

export function ComparisonTable({ comparison }: { comparison: Comparison }) {
  const areas = comparison.areas;
  const themeRows = Object.entries(comparison.theme_labels);
  const best = (values: (number | null)[]) => Math.max(...values.map((v) => v ?? -Infinity));

  return (
    <Card testId="comparison" title="Side by side" subtitle={`Weighting: ${comparison.preset}`}>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[var(--text-secondary)]">
              <th className="py-1 pr-2 font-medium" />
              {areas.map((a) => (
                <th key={a.code} className="py-1 pr-2 font-medium">{a.name}</th>
              ))}
            </tr>
          </thead>
          <tbody className="tabular-nums">
            <tr className="border-t border-[var(--border)]">
              <td className="py-1 pr-2 font-medium">Overall</td>
              {areas.map((a) => {
                const top = a.overall === best(areas.map((x) => x.overall));
                return <td key={a.code} className={`py-1 pr-2 text-sm ${top ? "font-semibold" : ""}`}>{a.overall?.toFixed(0) ?? "–"}</td>;
              })}
            </tr>
            {themeRows.map(([theme, label]) => {
              const values = areas.map((a) => (a.themes as Record<string, number | null>)[theme] ?? null);
              const top = best(values);
              return (
                <tr key={theme} className="border-t border-[var(--border)]">
                  <td className="py-1 pr-2 text-[var(--text-secondary)]">{label}</td>
                  {values.map((v, i) => (
                    <td key={areas[i].code} className="py-1 pr-2">
                      <span className="flex items-center gap-1.5">
                        <span className={`w-6 ${v === top ? "font-semibold" : ""}`}>{v?.toFixed(0) ?? "–"}</span>
                        <span className="h-1.5 w-12 rounded-r-[4px] bg-[var(--track)]">
                          <span className="block h-1.5 rounded-r-[4px] bg-[var(--series-1)]" style={{ width: `${v ?? 0}%` }} />
                        </span>
                      </span>
                    </td>
                  ))}
                </tr>
              );
            })}
            {Object.entries(comparison.indicator_labels).map(([id, label]) => (
              <tr key={id} className="border-t border-[var(--border)]">
                <td className="py-1 pr-2 text-[var(--text-secondary)]">{label}</td>
                {areas.map((a) => (
                  <td key={a.code} className="py-1 pr-2">
                    {formatValue((a.indicators as Record<string, number | null>)[id], UNITS[id] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Muted>Bold marks the best score in each row. Neighbourhoods and local authorities are population-weighted averages.</Muted>
    </Card>
  );
}
