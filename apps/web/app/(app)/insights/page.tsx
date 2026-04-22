import Link from "next/link";
import { Lightbulb } from "lucide-react";
import { BfCard } from "@/components/bidforge/bf-card";
import { BfContainer } from "@/components/bidforge/bf-container";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function InsightsPage() {
  return (
    <BfContainer>
      <header className="max-w-2xl">
        <h1 className="font-display text-3xl font-semibold tracking-[-0.03em] text-foreground">
          Insights
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          Cross-proposal trends, win themes, and quality signals will aggregate here from your runs. Until
          analytics are connected, this page stays intentionally empty.
        </p>
      </header>

      <BfCard className="mt-12 p-10 text-center md:p-14">
        <div className="mx-auto flex size-14 items-center justify-center rounded-2xl border border-border bg-muted/40 text-muted-foreground">
          <Lightbulb className="size-7" aria-hidden />
        </div>
        <p className="mx-auto mt-8 max-w-md text-base leading-relaxed text-muted-foreground">
          No insights yet. Complete a few proposal runs to unlock summaries here.
        </p>
        <Link
          href="/dashboard"
          className={cn(buttonVariants({ size: "lg" }), "mt-10 inline-flex h-12 rounded-xl px-8 text-[15px] font-semibold")}
        >
          Back to dashboard
        </Link>
      </BfCard>
    </BfContainer>
  );
}
