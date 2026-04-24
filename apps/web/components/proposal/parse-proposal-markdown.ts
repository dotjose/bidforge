export type ProposalSection = {
  title: string;
  body: string;
};

/** Split markdown-style ## headings into readable document sections. */
export function parseProposalMarkdown(markdown: string): ProposalSection[] {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  let start = 0;
  while (start < lines.length && lines[start].trim() === "") start += 1;
  if (start < lines.length) {
    const head = lines[start] ?? "";
    if (/^#\s+/.test(head) && !head.startsWith("##")) {
      start += 1;
      while (start < lines.length && lines[start].trim() === "") start += 1;
    }
  }
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

  for (const line of lines.slice(start)) {
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
