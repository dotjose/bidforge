import Link from "next/link";
import { cn } from "@/lib/utils";
import { Button, buttonVariants } from "@/components/ui/button";

type CtaButtonProps = {
  children: React.ReactNode;
  className?: string;
  variant?: "primary" | "secondary";
  href?: string;
  type?: "button" | "submit";
  onClick?: () => void;
};

export function CtaButton({
  children,
  className,
  variant = "primary",
  href,
  type = "button",
  onClick,
}: CtaButtonProps) {
  const primary =
    "h-12 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-8 text-[15px] font-semibold text-white shadow-md shadow-blue-500/20 transition hover:brightness-110 dark:from-blue-500 dark:to-violet-600";
  const secondary =
    "h-12 rounded-xl border border-border bg-background px-7 text-[15px] font-medium text-foreground shadow-sm transition hover:bg-muted/60";

  if (href) {
    return (
      <Link
        href={href}
        className={cn(
          buttonVariants({ size: "lg" }),
          variant === "primary" ? primary : secondary,
          "inline-flex items-center justify-center",
          className,
        )}
      >
        {children}
      </Link>
    );
  }

  return (
    <Button
      type={type}
      onClick={onClick}
      className={cn(variant === "primary" ? primary : secondary, className)}
    >
      {children}
    </Button>
  );
}
