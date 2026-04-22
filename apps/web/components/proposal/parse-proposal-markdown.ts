export type ProposalSection = {
  title: string;
  body: string;
};

/** Split markdown-style ## headings into readable document sections. */
export function parseProposalMarkdown(markdown: string): ProposalSection[] {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const sections: ProposalSection[] = [];
  let currentTitle = "";
  const bodyLines: string[] = [];

  const flush = () => {
    const body = bodyLines.join("\n").trim();
    if (currentTitle || body) {
      sections.push({
        title: currentTitle || "Overview",
        body,
      });
    }
    bodyLines.length = 0;
  };

  for (const line of lines) {
    if (line.startsWith("## ")) {
      flush();
      currentTitle = line.slice(3).trim();
    } else {
      bodyLines.push(line);
    }
  }
  flush();
  return sections.filter((s) => s.title || s.body);
}
