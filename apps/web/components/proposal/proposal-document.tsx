"use client";

import type { MemorySummary, SectionAttribution } from "@bidforge/web-sdk";
import { BookmarkPlus, ThumbsDown, ThumbsUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { parseProposalMarkdown } from "@/components/proposal/parse-proposal-markdown";
import { resolveMemoryRefs, titlesMatch } from "@/lib/memory-labels";
import { cn } from "@/lib/utils";

type ProposalDocumentProps = {
  markdown: string;
  sectionAttributions?: SectionAttribution[] | null;
  memorySummary?: MemorySummary | null;
  showSectionActions?: boolean;
  sectionActionsDisabled?: boolean;
  onSectionFeedback?: (title: string, body: string, kind: "positive" | "negative") => void | Promise<void>;
  onSaveSectionPattern?: (title: string, body: string) => void;
  /** Freelance replies hide heavy enterprise chrome for readability */
  presentation?: "enterprise" | "freelance";
  /** Long-form reader: larger type, hides RAG micro-lines */
  density?: "default" | "reader";
};

export function ProposalDocument({
  markdown,
  sectionAttributions,
  memorySummary,
  showSectionActions,
  sectionActionsDisabled,
  onSectionFeedback,
  onSaveSectionPattern,
  presentation = "enterprise",
  density = "default",
}: ProposalDocumentProps) {
  if (!markdown.trim()) {
    return (
      <p className="text-[17px] leading-relaxed text-muted-foreground">
        Paste a brief to generate your first proposal.
      </p>
    );
  }

  const sections = parseProposalMarkdown(markdown);

  const isFreelance = presentation === "freelance";
  const reader = density === "reader";

  return (
    <article
      className={cn(
        "space-y-10 md:space-y-12",
        isFreelance && !reader && "space-y-8 md:space-y-9",
        reader && "md:space-y-[2.5rem]",
      )}
    >
      {sections.map((section, i) => {
        const attr =
          sectionAttributions?.find((a) => titlesMatch(a.title, section.title)) ?? null;
        const covers =
          attr && attr.covers_requirements.length ? attr.covers_requirements : [];
        const basedMem =
          attr && attr.based_on_memory.length
            ? resolveMemoryRefs(attr.based_on_memory, memorySummary ?? undefined)
            : [];
        const body = section.body.trim();
        return (
          <section
            key={`${section.title}-${i}`}
            className={cn(
              "border-b border-border/50 pb-10 last:border-0 last:pb-0 md:pb-12",
              reader && "border-border/40 pb-12 md:pb-14 [content-visibility:auto]",
              isFreelance && !reader && "pb-8 md:pb-9",
            )}
          >
            {!isFreelance ? (
              <h3
                className={cn(
                  "font-display font-semibold tracking-[-0.02em] text-foreground",
                  reader
                    ? "text-[22px] leading-snug md:text-2xl"
                    : "text-lg md:text-[1.05rem]",
                )}
              >
                {section.title}
              </h3>
            ) : (
              <h3
                className={cn(
                  "font-display font-semibold tracking-[-0.01em] text-foreground/90",
                  reader ? "text-lg md:text-xl" : "text-[15px]",
                )}
              >
                {section.title}
              </h3>
            )}
            {!reader && !isFreelance && covers.length ? (
              <p className="mt-2 text-[12px] leading-relaxed text-muted-foreground">
                <span className="font-medium text-foreground/80">Covers: </span>
                {covers.join(", ")}
              </p>
            ) : null}
            {!reader && !isFreelance && basedMem.length ? (
              <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
                <span className="font-medium text-foreground/80">Signals: </span>
                {basedMem.join(" · ")}
              </p>
            ) : null}
            <div
              className={cn(
                "mt-4 max-w-prose space-y-4 text-[15px] leading-[1.7] text-muted-foreground",
                reader &&
                  "mt-5 max-w-none space-y-5 text-[17px] leading-[1.65] text-foreground/90 md:text-[17px]",
                isFreelance && !reader && "mt-3 space-y-3 text-[16px] leading-[1.65] text-foreground/90",
                isFreelance && reader && "mt-4 text-foreground/90",
              )}
            >
              {section.body.split(/\n\n+/).map((para, j) => (
                <p key={j}>{para.trim()}</p>
              ))}
            </div>
            {showSectionActions && body ? (
              <div className="mt-4 flex flex-wrap gap-2">
                {onSectionFeedback ? (
                  <>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-8 gap-1 px-2.5 text-[12px]"
                      disabled={sectionActionsDisabled}
                      onClick={() => void onSectionFeedback(section.title, body, "positive")}
                    >
                      <ThumbsUp className="size-3.5" aria-hidden />
                      Strong
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-8 gap-1 px-2.5 text-[12px]"
                      disabled={sectionActionsDisabled}
                      onClick={() => void onSectionFeedback(section.title, body, "negative")}
                    >
                      <ThumbsDown className="size-3.5" aria-hidden />
                      Weak
                    </Button>
                  </>
                ) : null}
                {onSaveSectionPattern ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-8 gap-1 px-2.5 text-[12px]"
                    disabled={sectionActionsDisabled}
                    onClick={() => onSaveSectionPattern(section.title, body)}
                  >
                    <BookmarkPlus className="size-3.5" aria-hidden />
                    Save as pattern
                  </Button>
                ) : null}
              </div>
            ) : null}
          </section>
        );
      })}
    </article>
  );
}
