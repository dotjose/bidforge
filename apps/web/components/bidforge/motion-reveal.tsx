"use client";

import { motion, useReducedMotion } from "framer-motion";

export type MotionRevealVariant = "fade-up" | "fade" | "slide-left" | "slide-right";

type MotionRevealProps = {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  variant?: MotionRevealVariant;
  /** When false, animates on mount (e.g. hero) instead of in-view */
  inView?: boolean;
};

const variantInitial = (variant: MotionRevealVariant) => {
  switch (variant) {
    case "fade":
      return { opacity: 0 };
    case "slide-left":
      return { opacity: 0, x: -32 };
    case "slide-right":
      return { opacity: 0, x: 32 };
    case "fade-up":
    default:
      return { opacity: 0, y: 20 };
  }
};

const variantAnimate = (variant: MotionRevealVariant) => {
  switch (variant) {
    case "fade":
      return { opacity: 1 };
    case "slide-left":
    case "slide-right":
      return { opacity: 1, x: 0 };
    case "fade-up":
    default:
      return { opacity: 1, y: 0 };
  }
};

export function MotionReveal({
  children,
  className,
  delay = 0,
  variant = "fade-up",
  inView = true,
}: MotionRevealProps) {
  const reduce = useReducedMotion();

  if (reduce) {
    return <div className={className}>{children}</div>;
  }

  const initial = variantInitial(variant);
  const animate = variantAnimate(variant);

  return (
    <motion.div
      initial={initial}
      {...(inView
        ? {
            whileInView: animate,
            viewport: { once: true, margin: "-64px" },
          }
        : {
            animate,
          })}
      transition={{ duration: 0.58, delay, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
