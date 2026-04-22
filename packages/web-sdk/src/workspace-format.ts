import type { NormalizedDocumentOutput } from "./types";

/** Flatten normalized sections into the same plain shape the API uses for extraction. */
export function normalizedDocumentToPlain(doc: NormalizedDocumentOutput): string {
  const parts = doc.sections
    .map((s) => `## ${s.name}\n\n${s.content}`.trim())
    .filter(Boolean);
  return parts.join("\n\n").trim();
}
