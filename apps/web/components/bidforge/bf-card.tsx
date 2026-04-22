import { cn } from "@/lib/utils";

type BfCardProps = {
  children: React.ReactNode;
  className?: string;
  /** Hover lift + shadow for clickable cards */
  interactive?: boolean;
  /** Softer surface (nested panels) */
  inset?: boolean;
};

export function BfCard({ children, className, interactive, inset }: BfCardProps) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-border/80 bg-card text-card-foreground shadow-sm",
        inset && "bg-muted/40 dark:bg-white/[0.03]",
        interactive &&
          "cursor-pointer transition duration-200 hover:border-border hover:shadow-md active:scale-[0.998]",
        className,
      )}
    >
      {children}
    </div>
  );
}
