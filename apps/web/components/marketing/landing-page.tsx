import Link from "next/link";
import { Show, SignInButton, SignUpButton } from "@clerk/nextjs";
import type { LucideIcon } from "lucide-react";
import {
  BadgeCheck,
  Blocks,
  Brain,
  Briefcase,
  Building2,
  CircleAlert,
  Cog,
  Download,
  FileWarning,
  Landmark,
  LayoutPanelLeft,
  ListRestart,
  PenTool,
  Puzzle,
  RefreshCw,
  Send,
  ShieldCheck,
  Target,
  Users,
} from "lucide-react";
import { BfContainer } from "@/components/bidforge/bf-container";
import { MotionReveal } from "@/components/bidforge/motion-reveal";
import { LandingProductPreview } from "@/components/marketing/landing-product-preview";
import { LandingSiteHeader } from "@/components/marketing/landing-site-header";
import { LandingWorkspaceMock } from "@/components/marketing/landing-workspace-mock";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const problemCards = [
  {
    title: "Unclear requirements",
    body: "Critical asks surface after legal, not before.",
    icon: Puzzle,
  },
  {
    title: "Rewriting effort",
    body: "Late nights reconciling format, facts, and versions.",
    icon: RefreshCw,
  },
  {
    title: "Review chaos",
    body: "Feedback in threads and slides—not the draft.",
    icon: FileWarning,
  },
] as const;

const solutionBlocks = [
  { title: "Route every brief", icon: Brain },
  { title: "One writer, one pass", icon: PenTool },
  { title: "Verify before you ship", icon: ShieldCheck },
] as const;

const workflowSteps = [
  {
    label: "Understand",
    icon: Download,
    line: "Job or RFP intelligence plus optional memory retrieval.",
  },
  {
    label: "Design",
    icon: Blocks,
    line: "Solution blueprint and positioning before prose.",
  },
  {
    label: "Draft + check",
    icon: Cog,
    line: "Single proposal write, then automated verification.",
  },
] as const;

const outcomes = [
  { title: "Earlier reviewer loops", body: "Legal sees intent sooner.", icon: ListRestart },
  { title: "Calmer deadline weeks", body: "Less last-minute assembly.", icon: Send },
  { title: "Fewer post-send surprises", body: "Less buyer friction after submit.", icon: Target },
] as const;

const trustLines = [
  { label: "Consulting teams", icon: Building2 },
  { label: "Agencies", icon: Briefcase },
  { label: "Enterprise bid teams", icon: Landmark },
] as const;

function SectionHeader({
  icon: Icon,
  eyebrow,
  title,
  subtitle,
  align = "left",
}: {
  icon?: LucideIcon;
  eyebrow: string;
  title: string;
  subtitle: string;
  align?: "left" | "center";
}) {
  return (
    <div
      className={cn(
        "max-w-3xl",
        align === "center" && "mx-auto text-center",
      )}
    >
      <div
        className={cn(
          "flex items-center gap-3",
          align === "center" && "justify-center",
        )}
      >
        {Icon ? (
          <span
            className="flex size-11 shrink-0 items-center justify-center rounded-xl border border-border/80 bg-muted/50 text-muted-foreground shadow-sm"
            aria-hidden
          >
            <Icon className="size-5 stroke-[1.5]" strokeWidth={1.5} />
          </span>
        ) : null}
        <p className={cn("bf-landing-eyebrow", Icon && "mb-0")}>{eyebrow}</p>
      </div>
      <h2 className={cn("bf-landing-h2 mt-4", align === "center" && "text-center")}>{title}</h2>
      <p
        className={cn(
          "bf-landing-body-muted mt-5 max-w-2xl text-pretty",
          align === "center" && "mx-auto",
        )}
      >
        {subtitle}
      </p>
    </div>
  );
}

export async function LandingPage() {
  return (
    <div className="relative min-h-screen bg-background text-foreground">
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 opacity-35 dark:opacity-100"
      >
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_55%_at_50%_-12%,rgba(59,130,246,0.12),transparent_58%)] dark:bg-[radial-gradient(ellipse_80%_55%_at_50%_-12%,rgba(59,130,246,0.16),transparent_58%)]" />
        <div className="bf-landing-grain absolute inset-0 mix-blend-multiply dark:mix-blend-overlay" />
      </div>

      <LandingSiteHeader />

      <main className="relative z-10">
        {/* Hero */}
        <section className="border-b border-border py-24 md:py-32 lg:py-40">
          <BfContainer>
            <div className="grid items-center gap-16 lg:grid-cols-2 lg:gap-20">
              <MotionReveal variant="slide-left" inView={false} className="max-w-xl">
                <h1 className="bf-landing-h1 text-pretty">
                  Build winning proposals, not documents.
                </h1>
                <p className="bf-landing-body-muted mt-8 max-w-lg text-pretty">
                  Paste a brief → get structured output → improve before submission.
                </p>
                <div className="mt-10 flex flex-col gap-4 sm:flex-row sm:items-center">
                  <Show when="signed-out">
                    <SignUpButton mode="modal">
                      <Button
                        className={cn(
                          buttonVariants({ variant: "default" }),
                          "bf-cta-press bf-cta-glow h-14 w-full min-w-[200px] rounded-2xl px-10 text-lg font-semibold shadow-md sm:w-auto",
                        )}
                      >
                        Start free
                      </Button>
                    </SignUpButton>
                    <a
                      href="#examples"
                      className={cn(
                        buttonVariants({ variant: "outline", size: "lg" }),
                        "bf-cta-press inline-flex h-14 w-full items-center justify-center rounded-2xl border-2 px-10 text-lg font-semibold sm:w-auto",
                      )}
                    >
                      View example
                    </a>
                  </Show>
                  <Show when="signed-in">
                    <Link
                      href="/proposal"
                      className={cn(
                        buttonVariants({ variant: "default" }),
                        "bf-cta-press bf-cta-glow inline-flex h-14 w-full min-w-[200px] items-center justify-center rounded-2xl px-10 text-lg font-semibold sm:w-auto",
                      )}
                    >
                      New proposal
                    </Link>
                    <Link
                      href="/proposal"
                      className={cn(
                        buttonVariants({ variant: "outline", size: "lg" }),
                        "bf-cta-press inline-flex h-14 w-full items-center justify-center rounded-2xl border-2 px-10 text-lg font-semibold sm:w-auto",
                      )}
                    >
                      Import RFP
                    </Link>
                  </Show>
                </div>
              </MotionReveal>

              <MotionReveal variant="slide-right" inView={false} delay={0.06} className="min-w-0">
                <div className="relative isolate">
                  <div
                    aria-hidden
                    className="pointer-events-none absolute -inset-8 rounded-[2rem] bg-[radial-gradient(ellipse_70%_60%_at_30%_20%,rgba(59,130,246,0.18),transparent_55%),radial-gradient(ellipse_55%_50%_at_85%_75%,rgba(139,92,246,0.14),transparent_50%)] opacity-90 blur-2xl dark:opacity-100"
                  />
                  <div className="relative">
                    <LandingWorkspaceMock
                      density="compact"
                      animateInView={false}
                      showFrameBranding
                    />
                  </div>
                </div>
              </MotionReveal>
            </div>
          </BfContainer>
        </section>

        {/* Problem */}
        <section id="product" className="border-b border-border py-24 md:py-32">
          <BfContainer>
            <SectionHeader
              icon={CircleAlert}
              eyebrow="Problem"
              title="Bids slip before the deadline."
              subtitle="Most drag is coordination—not writing talent."
            />
            <div className="mt-16 grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
              {problemCards.map((card, i) => (
                <MotionReveal key={card.title} delay={i * 0.05} className="h-full">
                  <div className="group/bf-card bf-hover-lift flex h-full flex-col rounded-2xl border border-border/80 bg-card/90 p-8 shadow-sm dark:border-white/[0.06] dark:bg-card/80">
                    <span className="flex size-12 items-center justify-center rounded-xl border border-border/60 bg-muted/50 text-muted-foreground transition-colors duration-300 group-hover/bf-card:border-blue-500/20 group-hover/bf-card:text-blue-600 dark:group-hover/bf-card:text-blue-400">
                      <card.icon className="size-6" aria-hidden strokeWidth={1.5} />
                    </span>
                    <h3 className="bf-landing-h3 mt-8">{card.title}</h3>
                    <p className="bf-landing-body-muted mt-3 flex-1">{card.body}</p>
                  </div>
                </MotionReveal>
              ))}
            </div>
          </BfContainer>
        </section>

        {/* Workflow + capabilities */}
        <section id="workflow" className="border-b border-border py-24 md:py-32">
          <BfContainer>
            <div className="grid gap-16 lg:grid-cols-12 lg:items-center lg:gap-20">
              <MotionReveal className="lg:col-span-5">
                <div className="flex items-center gap-3">
                  <span
                    className="flex size-11 shrink-0 items-center justify-center rounded-xl border border-border/80 bg-muted/50 text-muted-foreground shadow-sm"
                    aria-hidden
                  >
                    <Blocks className="size-5 stroke-[1.5]" strokeWidth={1.5} />
                  </span>
                  <p className="bf-landing-eyebrow mb-0">Workflow</p>
                </div>
                <h2 className="bf-landing-h2 mt-4 text-pretty">How work moves.</h2>
                <p className="bf-landing-body-muted mt-6 text-pretty">
                  Ingest, outline, draft—without the slide-deck detour.
                </p>
                <div className="mt-10 hidden rounded-2xl border border-border/70 bg-muted/25 p-6 shadow-sm dark:border-white/[0.06] dark:bg-white/[0.03] lg:block">
                  <div className="grid grid-cols-3 gap-3">
                    {workflowSteps.map((step) => (
                      <div
                        key={step.label}
                        className="group/wf flex flex-col items-center gap-2 rounded-xl border border-transparent bg-background/60 px-2 py-4 text-center transition-colors hover:border-border dark:bg-black/20"
                      >
                        <span className="flex size-10 items-center justify-center rounded-lg border border-border/60 bg-muted/40 text-muted-foreground transition-colors group-hover/wf:text-blue-600 dark:group-hover/wf:text-blue-400">
                          <step.icon className="size-5" aria-hidden strokeWidth={1.5} />
                        </span>
                        <span className="bf-landing-caption font-semibold text-foreground">
                          {step.label}
                        </span>
                        <p className="bf-landing-caption text-balance text-muted-foreground">{step.line}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </MotionReveal>
              <div className="grid gap-6 lg:col-span-7">
                {solutionBlocks.map((block, i) => (
                  <MotionReveal key={block.title} delay={0.04 + i * 0.06}>
                    <div className="group/bf-block bf-hover-lift grid gap-6 rounded-2xl border border-border/80 bg-background/95 p-8 shadow-sm sm:grid-cols-[auto_1fr] sm:items-center md:p-10 dark:border-white/[0.06] dark:bg-background/60">
                      <span className="flex size-14 shrink-0 items-center justify-center rounded-2xl border border-border/70 bg-muted/40 text-muted-foreground shadow-sm transition-colors duration-300 group-hover/bf-block:border-blue-500/25 group-hover/bf-block:text-blue-600 dark:group-hover/bf-block:text-blue-400">
                        <block.icon className="size-7" aria-hidden strokeWidth={1.5} />
                      </span>
                      <div>
                        <h3 className="bf-landing-h3">{block.title}</h3>
                      </div>
                    </div>
                  </MotionReveal>
                ))}
              </div>
            </div>
          </BfContainer>
        </section>

        {/* Product demo */}
        <section id="examples" className="border-b border-border py-24 md:py-32">
          <BfContainer>
            <SectionHeader
              icon={LayoutPanelLeft}
              eyebrow="Product"
              title="Source, draft, and signals in one frame."
              subtitle="Full-width layout your team actually ships with."
              align="center"
            />
            <MotionReveal className="mt-16 md:mt-20">
              <div className="relative rounded-[1.75rem] border border-border/60 bg-gradient-to-b from-muted/30 to-transparent p-[1px] shadow-sm dark:from-white/[0.04] dark:to-transparent">
                <div className="bf-workspace-grid-bg rounded-[1.65rem] bg-background/75 p-4 sm:p-6 md:bg-background/70 md:p-8 dark:bg-background/50">
                  <LandingProductPreview />
                </div>
              </div>
            </MotionReveal>
          </BfContainer>
        </section>

        {/* Outcomes */}
        <section className="py-24 md:py-32">
          <BfContainer>
            <SectionHeader
              icon={BadgeCheck}
              eyebrow="Outcomes"
              title="After week one."
              subtitle="Operational shifts—not feature claims."
            />
            <div className="mt-16 grid gap-6 md:grid-cols-3">
              {outcomes.map((o, i) => (
                <MotionReveal key={o.title} delay={i * 0.06}>
                  <div className="group/bf-card bf-hover-lift h-full rounded-2xl border border-border/80 bg-gradient-to-b from-muted/45 to-transparent p-8 shadow-sm md:p-10 dark:border-white/[0.06] dark:from-white/[0.04]">
                    <span className="flex size-11 items-center justify-center rounded-xl border border-border/60 bg-background/80 text-muted-foreground transition-colors group-hover/bf-card:text-blue-600 dark:bg-black/30 dark:group-hover/bf-card:text-blue-400">
                      <o.icon className="size-5" aria-hidden strokeWidth={1.5} />
                    </span>
                    <h3 className="bf-landing-h3 mt-6">{o.title}</h3>
                    <p className="bf-landing-body-muted mt-4">{o.body}</p>
                  </div>
                </MotionReveal>
              ))}
            </div>
          </BfContainer>
        </section>

        {/* Trust */}
        <section className="border-y border-border bg-muted/25 py-20 md:py-24 dark:bg-white/[0.03]">
          <BfContainer>
            <div className="flex items-center gap-3">
              <span
                className="flex size-11 shrink-0 items-center justify-center rounded-xl border border-border/80 bg-background/80 text-muted-foreground shadow-sm dark:bg-white/[0.04]"
                aria-hidden
              >
                <Users className="size-5 stroke-[1.5]" strokeWidth={1.5} />
              </span>
              <p className="bf-landing-eyebrow mb-0">Built for</p>
            </div>
            <ul className="mt-10 grid gap-4 sm:grid-cols-3">
              {trustLines.map((entry) => (
                <li key={entry.label}>
                  <div className="group/bf-card bf-hover-lift flex items-center gap-4 rounded-2xl border border-border/70 bg-background/80 p-5 shadow-sm dark:border-white/[0.06] dark:bg-background/40">
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-border/60 bg-muted/40 text-muted-foreground transition-colors group-hover/bf-card:text-blue-600 dark:group-hover/bf-card:text-blue-400">
                      <entry.icon className="size-5" aria-hidden strokeWidth={1.5} />
                    </span>
                    <span className="bf-landing-body font-medium text-foreground">{entry.label}</span>
                  </div>
                </li>
              ))}
            </ul>
          </BfContainer>
        </section>

        {/* Mid-page CTA */}
        <section className="border-t border-border py-24 md:py-32">
          <BfContainer>
            <div className="relative overflow-hidden rounded-3xl bg-foreground px-8 py-16 text-background shadow-2xl md:px-16 md:py-20 dark:bg-white dark:text-[#0B0F19]">
              <div
                aria-hidden
                className="pointer-events-none absolute -right-24 -top-24 size-80 rounded-full bg-white/10 blur-3xl dark:bg-black/10"
              />
              <div className="relative mx-auto max-w-3xl text-center">
                <h2 className="font-display text-4xl font-bold tracking-[-0.04em] md:text-5xl">
                  Ready when the next brief lands.
                </h2>
                <p className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-background/80 dark:text-[#0B0F19]/75 md:text-lg">
                  Paste a brief, generate a draft, and tighten it with built-in review before you send.
                </p>
                <div className="mt-10 flex flex-col items-stretch justify-center gap-4 sm:flex-row sm:items-center">
                  <Show when="signed-out">
                    <SignUpButton mode="modal">
                      <Button
                        variant="secondary"
                        className="bf-cta-press bf-cta-glow h-14 rounded-2xl bg-background px-10 text-lg font-semibold text-foreground hover:bg-background/90 dark:bg-[#0B0F19] dark:text-white dark:hover:bg-[#0B0F19]/90"
                      >
                        Start building your first proposal
                      </Button>
                    </SignUpButton>
                  </Show>
                  <Show when="signed-in">
                    <Link
                      href="/proposal"
                      className={cn(
                        buttonVariants({ variant: "secondary" }),
                        "bf-cta-press bf-cta-glow inline-flex h-14 items-center justify-center rounded-2xl bg-background px-10 text-lg font-semibold text-foreground dark:bg-[#0B0F19] dark:text-white",
                      )}
                    >
                      New proposal
                    </Link>
                  </Show>
                </div>
              </div>
            </div>
          </BfContainer>
        </section>
      </main>

      {/* Footer */}
      <footer id="docs" className="relative z-10 border-t border-border bg-muted/20 pt-20 pb-12 dark:bg-white/[0.02] md:pt-24">
        <BfContainer>
          <div className="grid gap-12 md:grid-cols-2 lg:grid-cols-12 lg:gap-10">
            <div className="lg:col-span-4">
              <p className="font-display text-xl font-bold tracking-[-0.03em]">BidForge</p>
              <p className="bf-landing-body-muted mt-4 max-w-sm">
                Proposal workspace for teams under deadline pressure.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Show when="signed-out">
                  <SignUpButton mode="modal">
                    <Button className="bf-cta-press bf-cta-glow h-11 rounded-xl px-6 text-base font-semibold">
                      Start building your first proposal
                    </Button>
                  </SignUpButton>
                </Show>
                <Show when="signed-in">
                  <Link
                    href="/proposal"
                    className={cn(
                      buttonVariants({ variant: "default" }),
                      "bf-cta-press bf-cta-glow inline-flex h-11 items-center justify-center rounded-xl px-6 text-base font-semibold",
                    )}
                  >
                    New proposal
                  </Link>
                </Show>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-10 sm:grid-cols-2 lg:col-span-8 lg:grid-cols-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                  Product
                </p>
                <ul className="mt-5 space-y-3">
                  <li>
                    <Link href="#product" className="bf-landing-body text-foreground/85 hover:text-foreground">
                      Overview
                    </Link>
                  </li>
                  <li>
                    <Link href="#workflow" className="bf-landing-body text-foreground/85 hover:text-foreground">
                      Workflow
                    </Link>
                  </li>
                  <li>
                    <Link href="#examples" className="bf-landing-body text-foreground/85 hover:text-foreground">
                      Examples
                    </Link>
                  </li>
                </ul>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                  Docs
                </p>
                <ul className="mt-5 space-y-3">
                  <li>
                    <span className="bf-landing-body text-muted-foreground">Getting started</span>
                  </li>
                  <li>
                    <span className="bf-landing-body text-muted-foreground">Workspace</span>
                  </li>
                  <li>
                    <span className="bf-landing-body text-muted-foreground">Reference</span>
                  </li>
                </ul>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                  Company
                </p>
                <ul className="mt-5 space-y-3">
                  <li>
                    <span className="bf-landing-body text-muted-foreground">About</span>
                  </li>
                  <li>
                    <span className="bf-landing-body text-muted-foreground">Careers</span>
                  </li>
                  <li>
                    <span className="bf-landing-body text-muted-foreground">Contact</span>
                  </li>
                </ul>
              </div>
              <div className="col-span-2 sm:col-span-1">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                  Legal
                </p>
                <ul className="mt-5 space-y-3">
                  <li>
                    <span className="bf-landing-body text-muted-foreground">Privacy</span>
                  </li>
                  <li>
                    <span className="bf-landing-body text-muted-foreground">Terms</span>
                  </li>
                  <li>
                    <span className="bf-landing-body text-muted-foreground">Security</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>

          <div className="mt-16 flex flex-col items-start justify-between gap-4 border-t border-border pt-10 md:flex-row md:items-center">
            <p className="bf-landing-caption">© {new Date().getFullYear()} BidForge. All rights reserved.</p>
            <Show when="signed-out">
              <SignInButton mode="modal">
                <button
                  type="button"
                  className="bf-landing-caption text-foreground underline-offset-4 hover:underline"
                >
                  Sign in
                </button>
              </SignInButton>
            </Show>
          </div>
        </BfContainer>
      </footer>
    </div>
  );
}
