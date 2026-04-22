import type { MemorySummary } from "@bidforge/web-sdk";

/** Short labels for PDF / exports — patterns only, never raw briefs or full documents. */
export function memorySummaryToInsightBullets(summary: MemorySummary | null | undefined): string[] {
  if (!summary) return [];
  const out: string[] = [];
  for (const w of summary.win_patterns ?? []) {
    const line = String(w.label ?? "").trim();
    if (line) out.push(line.slice(0, 220));
  }
  for (const w of summary.freelance_win_patterns ?? []) {
    if (String(w.outcome ?? "").toLowerCase() === "synthetic_seed") continue;
    const line = String(w.label ?? "").trim();
    if (line) out.push(line.slice(0, 220));
  }
  return out.slice(0, 8);
}
