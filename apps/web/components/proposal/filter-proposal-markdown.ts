import { parseProposalMarkdown } from "@/components/proposal/parse-proposal-markdown";

const BLOCKED_TITLE = [
  /^format notes$/i,
  /^appendix/i,
  /^debug/i,
  /^bidforge proposal/i,
  /^raw rfp/i,
  /^raw brief/i,
  /^metadata$/i,
  /^system/i,
  /^trace\b/i,
  /^log\b/i,
];

/** Strip non-client sections from model markdown before reader surfaces. */
export function filterProposalMarkdownForReader(markdown: string): string {
  const sections = parseProposalMarkdown(markdown);
  const kept = sections.filter((s) => {
    const t = s.title.trim();
    if (!t) return Boolean(s.body.trim());
    return !BLOCKED_TITLE.some((re) => re.test(t));
  });
  if (!kept.length) return "";
  return kept
    .map((s) => {
      const title = s.title.trim() || "Overview";
      return `## ${title}\n\n${s.body.trim()}`.trim();
    })
    .join("\n\n");
}
