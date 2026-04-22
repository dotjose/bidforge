import type { MemorySummary } from "@bidforge/web-sdk";

function norm(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

/** Map section titles between markdown headings and API attributions. */
export function titlesMatch(a: string, b: string): boolean {
  return norm(a) === norm(b);
}

/** Resolve `based_on_memory` entries to short human-readable lines using retrieval summary. */
export function resolveMemoryRefs(refs: string[], summary: MemorySummary | undefined): string[] {
  if (!summary || refs.length === 0) return refs;
  const catalog: { id: string; label: string }[] = [];
  for (const w of summary.win_patterns) {
    const id = String(w.id ?? "");
    const label = String(w.label ?? "Win pattern");
    const oc = String(w.outcome ?? "unknown");
    catalog.push({ id, label: `${label} (${oc})` });
  }
  for (const w of summary.freelance_win_patterns ?? []) {
    if (String(w.outcome ?? "").toLowerCase() === "synthetic_seed") continue;
    const id = String(w.id ?? "");
    const label = String(w.label ?? "Win pattern");
    const oc = String(w.outcome ?? "unknown");
    catalog.push({ id, label: `${label} (${oc})` });
  }
  return refs.map((ref) => {
    const r = ref.trim();
    if (!r) return ref;
    const byId = catalog.find((c) => c.id && (r === c.id || r.endsWith(c.id) || r.includes(c.id)));
    if (byId) return byId.label;
    return r;
  });
}
