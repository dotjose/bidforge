import type { ScoreBreakdown } from "@/components/bidforge/score-panel";
import type { ProposalPayload, TimelinePhase } from "@bidforge/web-sdk";

/** Map flattened API issues into score panel buckets. */
export function issuesToScoreBreakdown(issues: string[]): ScoreBreakdown {
  const coverage: string[] = [];
  const weakClaims: string[] = [];
  const risks: string[] = [];
  const memoryGrounding: string[] = [];
  for (const raw of issues) {
    if (raw.startsWith("freelance_fail:")) {
      weakClaims.push(raw.slice("freelance_fail:".length).trim());
    } else if (raw.startsWith("missing_requirement:")) {
      coverage.push(raw.slice("missing_requirement:".length).trim());
    } else if (raw.startsWith("compliance_risk:")) {
      risks.push(raw.slice("compliance_risk:".length).trim());
    } else if (raw.startsWith("missing_memory_usage:")) {
      memoryGrounding.push(raw.slice("missing_memory_usage:".length).trim());
    } else if (raw.startsWith("generic_language:")) {
      memoryGrounding.push(raw.slice("generic_language:".length).trim());
    } else if (raw.startsWith("generic_language_detection:")) {
      memoryGrounding.push(raw.slice("generic_language_detection:".length).trim());
    } else if (raw.startsWith("weak_claim:")) {
      weakClaims.push(raw.slice("weak_claim:".length).trim());
    } else if (raw.startsWith("deviation_from_win_patterns:")) {
      memoryGrounding.push(raw.slice("deviation_from_win_patterns:".length).trim());
    } else {
      weakClaims.push(raw);
    }
  }
  return { coverage, weakClaims, risks, memoryGrounding };
}

/** Turn structured API proposal into markdown for `ProposalDocument`. */
export function proposalPayloadToMarkdown(p: ProposalPayload): string {
  if (p.pipeline_mode === "freelance" && p.freelance) {
    const f = p.freelance;
    const hook = (f.hook ?? f.opening ?? "").trim();
    const need = (f.understanding_need ?? f.body ?? "").trim();
    const approach = (f.approach ?? "").trim();
    const experience = (f.relevant_experience ?? "").trim();
    const proofLegacy = (f.proof ?? "").trim();
    const expBody = experience || (!approach && proofLegacy ? proofLegacy : "");
    const cta = (f.call_to_action ?? f.closing ?? "").trim();
    const blocks = [
      `## Hook\n\n${hook}`.trim(),
      `## Understanding of your need\n\n${need}`.trim(),
      approach ? `## Approach\n\n${approach}`.trim() : "",
      expBody ? `## Relevant experience\n\n${expBody}`.trim() : "",
      `## Call to action\n\n${cta}`.trim(),
    ];
    return blocks.filter(Boolean).join("\n\n");
  }
  const s = p.sections;
  if (!s) return "";
  const blocks = [
    `## Executive summary\n\n${s.executive_summary || ""}`.trim(),
    `## Technical approach\n\n${s.technical_approach || ""}`.trim(),
    `## Delivery plan\n\n${s.delivery_plan || ""}`.trim(),
    `## Risk management\n\n${s.risk_management || ""}`.trim(),
  ];
  return blocks.filter(Boolean).join("\n\n");
}

export function timelineToMarkdown(timeline: TimelinePhase[]): string {
  if (!timeline.length) return "";
  const lines = timeline.map((t) => {
    const ph = (t.phase || "").trim();
    const dur = (t.duration || "").trim();
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
