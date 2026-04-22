import Link from "next/link";
import { FilePlus2 } from "lucide-react";
import { BfCard } from "@/components/bidforge/bf-card";
import { BfContainer } from "@/components/bidforge/bf-container";
import { SavedProposalRuns } from "@/components/proposal/saved-proposal-runs";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function DraftsPage() {
  return (
    <BfContainer>
      <header className="max-w-2xl">
        <h1 className="font-display text-3xl font-semibold tracking-[-0.03em] text-foreground">
          Drafts
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          Saved proposal runs from your workspace. Open any row to continue editing in the proposal
          workspace.
        </p>
      </header>

      <BfCard className="mt-10 p-6 md:p-8">
        <SavedProposalRuns
          emptyTitle="No saved runs"
          emptyBody=""
          showEmptyCta={false}
          className="text-left"
        />
      </BfCard>

      <div className="mt-10">
        <Link
          href="/proposal"
          className={cn(
            buttonVariants({ size: "lg" }),
            "inline-flex h-12 items-center gap-2 rounded-xl px-8 text-[15px] font-semibold",
          )}
        >
          <FilePlus2 className="size-5" aria-hidden />
          New proposal
        </Link>
      </div>
    </BfContainer>
  );
}
