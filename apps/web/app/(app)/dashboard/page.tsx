import Link from "next/link";
import { FilePlus2, Upload } from "lucide-react";
import { BfCard } from "@/components/bidforge/bf-card";
import { BfContainer } from "@/components/bidforge/bf-container";
import { SavedProposalRuns } from "@/components/proposal/saved-proposal-runs";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function DashboardPage() {
  return (
    <BfContainer>
      <header className="max-w-2xl">
        <h1 className="font-display text-3xl font-semibold tracking-[-0.03em] text-foreground">
          Dashboard
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          Start proposals, reopen saved runs, and keep quality high before you submit.
        </p>
      </header>

      <div className="mt-12 grid gap-6 md:grid-cols-2 md:gap-8">
        <BfCard className="relative overflow-hidden p-8 md:p-10">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-blue-500/10 via-transparent to-violet-500/10 dark:from-blue-500/14 dark:to-violet-500/12"
          />
          <div className="relative z-10">
            <h2 className="font-display text-xl font-semibold tracking-[-0.02em] text-foreground">
              New proposal
            </h2>
            <p className="mt-3 text-base leading-relaxed text-muted-foreground">
              Paste a brief and generate a structured draft with review and timeline in one flow.
            </p>
            <Link
              href="/proposal"
              className={cn(
                buttonVariants({ size: "lg" }),
                "mt-8 inline-flex h-12 items-center gap-2 rounded-xl px-8 text-[15px] font-semibold",
              )}
            >
              <FilePlus2 className="size-5" aria-hidden />
              New proposal
            </Link>
          </div>
        </BfCard>

        <BfCard className="p-8 md:p-10">
          <h2 className="font-display text-xl font-semibold tracking-[-0.02em] text-foreground">
            Import RFP
          </h2>
          <p className="mt-3 text-base leading-relaxed text-muted-foreground">
            Bring text from email, portals, or a plain-text export—then refine in the workspace.
          </p>
          <Link
            href="/proposal"
            className={cn(
              buttonVariants({ variant: "outline", size: "lg" }),
              "mt-8 inline-flex h-12 items-center gap-2 rounded-xl border-2 px-8 text-[15px] font-semibold",
            )}
          >
            <Upload className="size-5" aria-hidden />
            Open workspace
          </Link>
        </BfCard>
      </div>

      <section className="mt-16 md:mt-20">
        <h2 className="font-display text-xl font-semibold tracking-[-0.02em] text-foreground">
          Recent proposals
        </h2>
        <BfCard className="mt-6 p-6 md:p-8">
          <SavedProposalRuns
            emptyTitle="No proposals yet"
            emptyBody="Generate a proposal from the workspace — completed runs appear here automatically."
            className="text-left"
          />
        </BfCard>
      </section>
    </BfContainer>
  );
}
