"use client";

import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/utils";

type Density = "compact" | "comfortable";

type LandingWorkspaceMockProps = {
  id?: string;
  density?: Density;
  className?: string;
  /** Animate on scroll into view (section demo). Hero passes false and wraps with its own motion. */
  animateInView?: boolean;
  /** Hero illustration: branded chrome title + tighter badge stack */
  showFrameBranding?: boolean;
};

function UiBadge({
  children,
  tone,
}: {
  children: React.ReactNode;
  tone: "risk" | "warning" | "ready" | "draft" | "structured";
}) {
  const tones = {
    risk: "border-red-500/25 bg-red-500/[0.08] text-red-800 dark:border-red-500/30 dark:bg-red-500/15 dark:text-red-100/95",
    warning:
      "border-amber-500/30 bg-amber-500/[0.1] text-amber-950 dark:border-amber-500/25 dark:bg-amber-500/12 dark:text-amber-50/95",
    ready:
      "border-emerald-500/25 bg-emerald-500/[0.1] text-emerald-950 dark:border-emerald-500/25 dark:bg-emerald-500/12 dark:text-emerald-50/95",
    draft: "border-blue-500/20 bg-blue-500/[0.08] text-blue-950 dark:border-blue-500/25 dark:bg-blue-500/10 dark:text-blue-50/95",
    structured:
      "border-sky-500/20 bg-sky-500/[0.07] text-sky-950 dark:border-sky-500/20 dark:bg-sky-500/10 dark:text-sky-50/95",
  } as const;

  return (
    <span
      className={cn(
        "whitespace-nowrap rounded-full border px-2.5 py-1 text-[10px] font-semibold tracking-wide sm:text-xs",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}

export function LandingWorkspaceMock({
  id,
  density = "comfortable",
  className,
  animateInView = true,
  showFrameBranding = false,
}: LandingWorkspaceMockProps) {
  const reduce = useReducedMotion();
  const [focus, setFocus] = useState<"source" | "workspace">("workspace");

  const compact = density === "compact";
  const mono = compact ? "text-[13px] leading-relaxed sm:text-sm" : "text-sm leading-relaxed sm:text-base";
  const panelPad = compact ? "p-4 sm:p-5" : "p-6 sm:p-8";
  const sectionTitle = compact
    ? "font-display text-base font-semibold tracking-[-0.02em] sm:text-lg"
    : "font-display text-lg font-semibold tracking-[-0.02em] sm:text-xl";
  const sectionBody = compact ? "mt-2 text-sm leading-relaxed sm:text-base" : "mt-3 text-base leading-relaxed";

  const shellMotion = animateInView && !reduce
    ? {
        initial: { opacity: 0, y: 20 } as const,
        whileInView: { opacity: 1, y: 0 } as const,
        viewport: { once: true, margin: "-64px" } as const,
        transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] } as const,
      }
    : {};

  const gridPanel = "bf-workspace-grid-bg";

  return (
    <motion.div
      id={id}
      {...shellMotion}
      whileHover={reduce ? undefined : { scale: 1.006 }}
      transition={{ type: "spring", stiffness: 420, damping: 28 }}
      className={cn(
        "group/mock overflow-hidden rounded-2xl border border-border/80 bg-card/95 shadow-[0_40px_100px_-48px_rgba(0,0,0,0.32),0_0_0_1px_rgba(255,255,255,0.04)_inset] dark:border-white/[0.08] dark:bg-card dark:shadow-[0_48px_120px_-52px_rgba(0,0,0,0.78),inset_0_1px_0_0_rgba(255,255,255,0.06)]",
        compact ? "rounded-xl sm:rounded-2xl" : "rounded-2xl",
        className,
      )}
    >
      {/* Window chrome */}
      <div className="flex flex-col gap-3 border-b border-border/80 bg-muted/50 px-4 py-3 dark:bg-white/[0.04] sm:px-5 sm:py-3.5">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="size-2.5 rounded-full bg-red-400/90" />
            <span className="size-2.5 rounded-full bg-amber-400/90" />
            <span className="size-2.5 rounded-full bg-emerald-400/90" />
          </div>
          <div className="flex min-w-0 flex-1 flex-col gap-0.5 sm:flex-row sm:items-center sm:gap-3">
            {showFrameBranding ? (
              <>
                <p className="truncate font-display text-sm font-semibold tracking-[-0.02em] text-foreground sm:text-[15px]">
                  BidForge workspace
                </p>
                <span className="hidden font-mono text-[11px] text-muted-foreground sm:inline sm:text-xs">
                  Workspace · your RFP
                </span>
              </>
            ) : (
                <span className="truncate font-mono text-xs text-muted-foreground sm:text-[13px]">
                Workspace · your RFP
              </span>
            )}
            {!reduce ? (
              <span className="relative flex h-2 w-2 shrink-0">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400/35 opacity-75 motion-reduce:animate-none" />
                <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
              </span>
            ) : (
              <span className="size-2 shrink-0 rounded-full bg-emerald-500" aria-hidden />
            )}
            <span className="text-[11px] font-medium text-emerald-700 dark:text-emerald-300/90">Live</span>
          </div>
          <div className="flex w-full flex-wrap items-center gap-1.5 sm:ml-auto sm:w-auto sm:justify-end">
            <UiBadge tone="risk">Risk detected</UiBadge>
            <UiBadge tone="warning">Missing requirement</UiBadge>
            <UiBadge tone="ready">Review ready</UiBadge>
            <UiBadge tone="draft">Draft</UiBadge>
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-2">
        <motion.button
          type="button"
          aria-label="Source panel — select to focus source material"
          onClick={() => setFocus("source")}
          whileTap={reduce ? undefined : { scale: 0.995 }}
          className={cn(
            "group/panel relative border-b border-border/80 text-left transition-[box-shadow,background-color] duration-300 lg:border-b-0 lg:border-r lg:border-border/80",
            panelPad,
            gridPanel,
            focus === "source"
              ? "bg-muted/50 shadow-[inset_0_0_0_1px_rgba(59,130,246,0.22),inset_0_0_48px_rgba(59,130,246,0.06)] dark:bg-white/[0.05] dark:shadow-[inset_0_0_0_1px_rgba(96,165,250,0.25),inset_0_0_48px_rgba(59,130,246,0.08)]"
              : "bg-muted/15 hover:bg-muted/30 dark:bg-transparent dark:hover:bg-white/[0.04]",
          )}
        >
          {!reduce ? (
            <motion.div
              aria-hidden
              className="pointer-events-none absolute bottom-4 left-5 right-5 h-px bg-gradient-to-r from-transparent via-blue-500/35 to-transparent"
              animate={{ opacity: focus === "source" ? [0.5, 1, 0.5] : 0.35 }}
              transition={{ duration: 2.6, repeat: Infinity, ease: "easeInOut" }}
            />
          ) : null}
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground sm:text-[13px]">
              Source
            </p>
            <UiBadge tone="structured">Inbox</UiBadge>
          </div>
          <div
            className={cn(
              "relative mt-4 max-h-[min(280px,42vh)] space-y-3 overflow-y-auto rounded-xl border border-border/70 bg-background/80 p-4 font-mono text-muted-foreground shadow-inner dark:border-white/[0.06] dark:bg-[#0B0F19]/95",
              mono,
              compact ? "sm:max-h-[320px]" : "sm:max-h-[360px]",
            )}
          >
            <p className="text-foreground/90">Your RFP or brief appears here.</p>
            <p className="opacity-90">
              BidForge runs extraction, structuring, mandatory memory retrieval, and grounded drafting
              against your indexed wins — not generic templates.
            </p>
            {!reduce ? (
              <p className="relative inline-flex items-center gap-1 font-sans text-foreground/70">
                <span
                  aria-hidden
                  className="inline-block size-3.5 rounded-sm border border-blue-500/45 bg-blue-500/[0.12] shadow-[0_0_0_3px_rgba(59,130,246,0.1)]"
                />
                <span className="inline-block h-3.5 w-0.5 animate-pulse bg-blue-500 motion-reduce:animate-none" />
              </p>
            ) : null}
          </div>
        </motion.button>

        <motion.button
          type="button"
          aria-label="Output panel — select to focus workspace"
          onClick={() => setFocus("workspace")}
          whileTap={reduce ? undefined : { scale: 0.995 }}
          className={cn(
            "group/panel relative text-left transition-[box-shadow,background-color] duration-300",
            panelPad,
            gridPanel,
            focus === "workspace"
              ? "bg-background/90 shadow-[inset_0_0_0_1px_rgba(59,130,246,0.2),inset_0_0_56px_rgba(139,92,246,0.06)] dark:bg-white/[0.06] dark:shadow-[inset_0_0_0_1px_rgba(96,165,250,0.22),inset_0_0_56px_rgba(139,92,246,0.07)]"
              : "bg-background/60 hover:bg-background/85 dark:bg-white/[0.02] dark:hover:bg-white/[0.05]",
          )}
        >
          {!reduce ? (
            <motion.div
              aria-hidden
              className="pointer-events-none absolute inset-0 bg-gradient-to-br from-blue-500/[0.08] via-transparent to-violet-500/[0.07]"
              animate={{ opacity: focus === "workspace" ? [0.45, 0.92, 0.45] : 0.32 }}
              transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
            />
          ) : null}
          {!reduce && focus === "workspace" ? (
            <motion.div
              aria-hidden
              className="pointer-events-none absolute bottom-8 right-8 size-24 rounded-full border border-blue-500/20 bg-blue-500/[0.06] blur-md"
              animate={{ opacity: [0.4, 0.75, 0.4], scale: [1, 1.05, 1] }}
              transition={{ duration: 2.8, repeat: Infinity, ease: "easeInOut" }}
            />
          ) : null}
          <div className="relative">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground sm:text-[13px]">
                Output
              </p>
              <UiBadge tone="structured">Outline</UiBadge>
            </div>
            <div
              className={cn(
                "mt-4 divide-y divide-border/60",
                !compact && "mt-6",
              )}
            >
              <section className="pb-6">
                <h3 className={sectionTitle}>Structured output</h3>
                <p className={cn(sectionBody, "text-muted-foreground")}>
                  Proposal, timeline, and verifier issues render from your API response — no seeded
                  sample proposals in the product UI.
                </p>
              </section>
              <section className="py-6">
                <h3 className={sectionTitle}>Memory column</h3>
                <p className={cn(sectionBody, "text-muted-foreground")}>
                  Similar wins, patterns, and methodology appear only when your tenant has indexed
                  memory in Supabase.
                </p>
              </section>
            </div>
          </div>
        </motion.button>
      </div>
    </motion.div>
  );
}
