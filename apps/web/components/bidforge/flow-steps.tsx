"use client";

import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

export type FlowStepItem = {
  step: string;
  title: string;
  description: string;
};

type FlowStepsProps = {
  steps: FlowStepItem[];
  className?: string;
};

export function FlowSteps({ steps, className }: FlowStepsProps) {
  const reduce = useReducedMotion();

  return (
    <div className={cn("w-full", className)}>
      <div className="flex flex-col gap-6 md:flex-row md:items-stretch md:gap-0">
        {steps.map((item, index) => (
          <div key={item.step} className="flex flex-1 items-stretch gap-0">
            <motion.div
              className="min-w-0 flex-1"
              initial={reduce ? false : { opacity: 0, y: 14 }}
              whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-32px" }}
              transition={{
                duration: 0.45,
                delay: index * 0.07,
                ease: [0.22, 1, 0.36, 1],
              }}
            >
              <div className="relative h-full overflow-hidden rounded-2xl border border-border bg-card p-6 shadow-sm before:pointer-events-none before:absolute before:inset-x-0 before:top-0 before:h-0.5 before:bg-gradient-to-r before:from-blue-500/0 before:via-blue-500/40 before:to-violet-500/0 md:px-6 md:py-7">
                <div className="flex items-center gap-3">
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-600 to-violet-600 text-sm font-bold text-white shadow-md shadow-blue-500/25">
                    {item.step}
                  </span>
                  <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                    Step {item.step}
                  </span>
                </div>
                <h3 className="mt-5 font-display text-lg font-semibold tracking-[-0.02em] text-foreground">
                  {item.title}
                </h3>
                <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">
                  {item.description}
                </p>
              </div>
            </motion.div>
            {index < steps.length - 1 ? (
              <div
                className="hidden shrink-0 items-center justify-center px-1 md:flex"
                aria-hidden
              >
                <ArrowRight className="size-5 text-muted-foreground/40" />
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
