import type { ScoreBreakdown } from "@/components/bidforge/score-panel";
import type { ProposalPayload, ProposalPublicRunResponse, ProposalSections, TimelinePhase } from "@bidforge/web-sdk";

const UNTITLED = "Untitled proposal";

const GENERIC_API_TITLES = new Set([
  "untitled proposal",
  "proposal",
  "new proposal",
  "rfp response",
  "proposal from your brief",
]);

/** Strip lightweight markdown from API strings (timeline phases, verifier lines) for reader UI. */
export function stripReaderMarkdownArtifacts(text: string): string {
  let t = (text || "").trim();
  t = t.replace(/\*\*([^*]+)\*\*/g, "$1");
  t = t.replace(/\*([^*]+)\*/g, "$1");
  t = t.replace(/^[\s#>*-]+/gm, "").replace(/\s+/g, " ");
  return t.trim();
}

/** Browser / PDF export title when the user has not set one and the API title is generic. */
export function fallbackProposalExportTitle(
  jobBrief: string,
  proposalMarkdown: string,
  apiTitle?: string | null,
): string {
  const t = (apiTitle ?? "").trim();
  const low = t.toLowerCase();
  if (t.length > 2 && low !== UNTITLED.toLowerCase() && !GENERIC_API_TITLES.has(low)) {
    return t.slice(0, 200);
  }
  const briefLine = jobBrief
    .split(/\r?\n/)
    .map((l) => l.trim())
    .find((l) => l.length > 10 && !l.startsWith("#"));
  if (briefLine) {
    return briefLine.replace(/^[\s#>*-]+/, "").slice(0, 120);
  }
  const m = proposalMarkdown.match(/^##\s+(.+)$/m);
  if (m?.[1]?.trim()) {
    return m[1].trim().slice(0, 120);
  }
  return "Proposal";
}

/** Bare verifier tokens (no `prefix:`) — map to client-facing copy; never show raw slugs in UI. */
const VERIFIER_SLUG_HINTS: Record<string, string> = {
  generic_tone: "Opening reads generic — add one concrete, client-specific proof point.",
  unclear_value: "Value proposition is vague — tie benefits to outcomes named in the brief.",
  generic_language: "Replace stock phrasing with role-specific detail the client can verify.",
  generic_language_detection: "Several passages read like boilerplate — tighten with specifics.",
  generic_tone_detection: "Opening tone feels template-like — lead with relevance to this engagement.",
};

function humanizeBareVerifierLine(raw: string): string {
  const t = raw.trim();
  if (!t) return t;
  const low = t.toLowerCase();
  if (VERIFIER_SLUG_HINTS[low]) return VERIFIER_SLUG_HINTS[low];
  if (/^[a-z][a-z0-9_]*$/i.test(t) && t.length < 56) {
    return t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
  return t;
}

/** Map flattened API issues into score panel buckets. */
export function issuesToScoreBreakdown(issues: string[]): ScoreBreakdown {
  const coverage: string[] = [];
  const weakClaims: string[] = [];
  const risks: string[] = [];
  const memoryGrounding: string[] = [];
  for (const raw of issues) {
    const low = raw.toLowerCase();
    if (low.startsWith("freelance_fail:")) {
      weakClaims.push(stripReaderMarkdownArtifacts(raw.slice(raw.indexOf(":") + 1).trim()));
    } else if (low.startsWith("missing_requirement:")) {
      coverage.push(stripReaderMarkdownArtifacts(raw.slice(raw.indexOf(":") + 1).trim()));
    } else if (low.startsWith("compliance_risk:")) {
      risks.push(stripReaderMarkdownArtifacts(raw.slice(raw.indexOf(":") + 1).trim()));
    } else if (low.startsWith("missing_memory_usage:")) {
      memoryGrounding.push(stripReaderMarkdownArtifacts(raw.slice(raw.indexOf(":") + 1).trim()));
    } else if (low.startsWith("generic_language:")) {
      memoryGrounding.push(humanizeBareVerifierLine(raw.slice(raw.indexOf(":") + 1).trim()));
    } else if (low.startsWith("generic_language_detection:")) {
      memoryGrounding.push(humanizeBareVerifierLine(raw.slice(raw.indexOf(":") + 1).trim()));
    } else if (low.startsWith("weak_claim:")) {
      weakClaims.push(stripReaderMarkdownArtifacts(raw.slice(raw.indexOf(":") + 1).trim()));
    } else if (low.startsWith("deviation_from_win_patterns:")) {
      memoryGrounding.push(stripReaderMarkdownArtifacts(raw.slice(raw.indexOf(":") + 1).trim()));
    } else if (low.startsWith("generic_tone:") || low === "generic_tone") {
      weakClaims.push(
        low.includes(":")
          ? humanizeBareVerifierLine(raw.slice(raw.indexOf(":") + 1).trim())
          : VERIFIER_SLUG_HINTS.generic_tone,
      );
    } else if (low.startsWith("unclear_value:") || low === "unclear_value") {
      weakClaims.push(
        low.includes(":")
          ? humanizeBareVerifierLine(raw.slice(raw.indexOf(":") + 1).trim())
          : VERIFIER_SLUG_HINTS.unclear_value,
      );
    } else {
      weakClaims.push(humanizeBareVerifierLine(raw));
    }
  }
  return { coverage, weakClaims, risks, memoryGrounding };
}

/** Client-only markdown from the strict public run contract (no verifier / memory dumps). */
export function publicRunToMarkdown(run: ProposalPublicRunResponse): string {
  const blocks: string[] = [];
  const docTitle = (run.title || "").trim();
  if (docTitle) {
    blocks.push(`# ${docTitle}`);
  }
  const ex = (run.executive_summary || "").trim();
  if (ex) blocks.push(`## Opening\n\n${ex}`);
  for (const sec of run.sections || []) {
    const t = (sec.title || "").trim();
    const c = (sec.content || "").trim();
    if (!t && !c) continue;
    if (t) blocks.push(`## ${t}\n\n${c}`);
    else if (c) blocks.push(c);
  }
  return blocks.join("\n\n").trim();
}

/** Map public sections to PDF / export keys (legacy fields filled for backward compatibility). */
export function publicRunToProposalSections(run: ProposalPublicRunResponse): ProposalSections {
  const pick = (label: string) =>
    (run.sections || []).find((s) => s.title.trim().toLowerCase() === label.toLowerCase())?.content.trim() ?? "";
  const opening = (run.executive_summary || "").trim() || pick("Opening");
  const understanding = pick("Understanding") || pick("What I'll Deliver");
  const solution = pick("Solution");
  const exec = pick("Execution Plan");
  const tl = pick("Timeline");
  const del = pick("Deliverables");
  const rel = pick("Relevant Experience");
  const risk = pick("Risk Management") || pick("Risk Reduction") || pick("Risks & Mitigation");
  const cta = pick("Next Step") || pick("Call to Action");
  return {
    opening,
    understanding,
    solution,
    execution_plan: exec,
    timeline: tl,
    deliverables: del,
    experience: rel,
    risks: risk,
    next_step: cta,
    hook: opening,
    what_ill_deliver: understanding,
    timeline_block: tl,
    deliverables_block: del,
    risk_reduction: risk,
    relevant_experience: rel,
    call_to_action: cta,
    executive_summary: opening,
    technical_approach: exec,
    delivery_plan: [tl, del].filter(Boolean).join("\n\n").trim(),
    risk_management: [risk, rel, cta].filter(Boolean).join("\n\n").trim(),
  };
}

/** Turn structured API proposal into markdown for `ProposalDocument`. */
export function proposalPayloadToMarkdown(p: ProposalPayload): string {
  if (p.pipeline_mode === "freelance" && p.freelance) {
    const f = p.freelance;
    const open = (f.opening ?? f.hook ?? "").trim();
    const need = (f.understanding ?? f.understanding_need ?? f.body ?? "").trim();
    const sol = (f.solution ?? f.approach ?? "").trim();
    const experience = (f.experience ?? f.relevant_experience ?? "").trim();
    const proofLegacy = (f.proof ?? "").trim();
    const expBody = experience || (!sol && proofLegacy ? proofLegacy : "");
    const cta = (f.next_step ?? f.call_to_action ?? f.closing ?? "").trim();
    const tasks = (f.execution_tasks ?? []).map((t) => `- ${String(t).trim()}`).filter(Boolean).join("\n");
    const tw = (f.timeline ?? f.timeline_weeks ?? [])
      .map((t) => String(t).trim())
      .filter(Boolean)
      .join("\n");
    const dl = (f.deliverables ?? f.deliverables_list ?? [])
      .map((d) => `- ${String(d).trim()}`)
      .filter(Boolean)
      .join("\n");
    const rm = (f.risks ?? f.risks_mitigation ?? "").trim();
    const blocks = [
      open ? `## Opening\n\n${open}`.trim() : "",
      need ? `## Understanding\n\n${need}`.trim() : "",
      sol ? `## Solution\n\n${sol}`.trim() : "",
      tasks ? `## Execution plan\n\n${tasks}`.trim() : "",
      tw ? `## Timeline\n\n${tw}`.trim() : "",
      dl ? `## Deliverables\n\n${dl}`.trim() : "",
      rm ? `## Risk management\n\n${rm}`.trim() : "",
      expBody ? `## Relevant experience\n\n${expBody}`.trim() : "",
      cta ? `## Next step\n\n${cta}`.trim() : "",
    ];
    return blocks.filter(Boolean).join("\n\n");
  }
  const s = p.sections;
  if (!s) return "";
  const open = s.opening || s.hook || s.executive_summary || "";
  const what = s.understanding || s.what_ill_deliver || "";
  const sol = s.solution || "";
  const exec = s.execution_plan || s.technical_approach || "";
  const tl = s.timeline || s.timeline_block || "";
  const del = s.deliverables || s.deliverables_block || "";
  const rel = s.experience || s.relevant_experience || "";
  const risk = s.risks || s.risk_reduction || "";
  const cta = s.next_step || s.call_to_action || "";
  const hasCanon = Boolean(open || what || sol || exec || tl || del || rel || risk || cta);
  const blocks = [
    open ? `## Opening\n\n${open}`.trim() : "",
    what ? `## Understanding\n\n${what}`.trim() : "",
    sol ? `## Solution\n\n${sol}`.trim() : "",
    exec ? `## Execution plan\n\n${exec}`.trim() : "",
    tl ? `## Timeline\n\n${tl}`.trim() : "",
    del ? `## Deliverables\n\n${del}`.trim() : "",
    risk ? `## Risk management\n\n${risk}`.trim() : "",
    rel ? `## Relevant experience\n\n${rel}`.trim() : "",
    cta ? `## Next step\n\n${cta}`.trim() : "",
  ];
  if (hasCanon) {
    return blocks.filter(Boolean).join("\n\n");
  }
  return [
    open ? `## Opening\n\n${open}`.trim() : "",
    s.technical_approach ? `## Execution plan\n\n${s.technical_approach}`.trim() : "",
    s.delivery_plan ? `## Timeline & deliverables\n\n${s.delivery_plan}`.trim() : "",
    s.risk_management ? `## Proof & risks\n\n${s.risk_management}`.trim() : "",
  ]
    .filter(Boolean)
    .join("\n\n");
}

/** Markdown body for timeline (single section). Prefer `ProposalTimelineSection` in the app shell. */
export function timelineToMarkdown(timeline: TimelinePhase[]): string {
  if (!timeline.length) return "";
  const lines = timeline.map((t) => {
    const ph = stripReaderMarkdownArtifacts(t.phase || "");
    const dur = stripReaderMarkdownArtifacts(t.duration || "");
    if (!ph && !dur) return "";
    if (ph && dur) return `- **${ph}** — ${dur}`;
    return `- **${ph || dur}**`;
  });
  const body = lines.filter(Boolean).join("\n");
  return `## Timeline\n\n${body}`;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Open a print dialog with proposal + optional appendix (Save as PDF in the browser). */
export function printProposalAsPdf(
  mainMarkdown: string,
  appendixMarkdown?: string,
  documentTitle?: string,
): void {
  const w = window.open("", "_blank");
  if (!w) return;
  const appendix = appendixMarkdown?.trim()
    ? `<hr/><div class="appendix">${escapeHtml(appendixMarkdown).replace(/\n/g, "<br/>")}</div>`
    : "";
  const title = escapeHtml((documentTitle || "Proposal").trim() || "Proposal");
  w.document.write(
    `<!DOCTYPE html><html><head><meta charset="utf-8"/><title>${title}</title>` +
      `<style>body{font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;line-height:1.55;color:#111}` +
      `.appendix{font-size:0.92rem;color:#444;margin-top:2rem}</style></head><body>` +
      `<div class="main">${escapeHtml(mainMarkdown).replace(/\n/g, "<br/>")}</div>${appendix}` +
      `</body></html>`,
  );
  w.document.close();
  w.focus();
  w.print();
}
