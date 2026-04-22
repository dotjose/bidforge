import Link from "next/link";
import { FilePlus2 } from "lucide-react";
import { BfCard } from "@/components/bidforge/bf-card";
import { BfContainer } from "@/components/bidforge/bf-container";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function MemoryPage() {
  return (
    <BfContainer>
      <header className="max-w-2xl">
        <h1 className="font-display text-3xl font-semibold tracking-[-0.03em] text-foreground">
          Intelligence memory
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          Your winning patterns, past proposals, and reusable blocks surface here when they strengthen a
          run. Each item is retrieved for a specific brief—nothing is fabricated for display.
        </p>
      </header>

      <BfCard className="mt-12 p-10 md:p-14">
        <p className="max-w-xl text-base leading-relaxed text-muted-foreground">
          No saved intelligence yet. Generate proposals and confirm strong sections to build a private
          library that improves the next draft.
        </p>
        <Link
          href="/proposal"
          className={cn(
            buttonVariants({ size: "lg" }),
            "mt-10 inline-flex h-12 items-center gap-2 rounded-xl px-8 text-[15px] font-semibold",
          )}
        >
          <FilePlus2 className="size-5" aria-hidden />
          New proposal
        </Link>
      </BfCard>
    </BfContainer>
  );
}
