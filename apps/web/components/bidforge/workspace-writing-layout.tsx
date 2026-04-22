"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { GripVertical, PanelRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const SPLIT_STORAGE_KEY = "bf-workspace-left-pct";
const DEFAULT_LEFT_PCT = 40;
const MIN_LEFT_PCT = 28;
const MAX_LEFT_PCT = 58;

export type WorkspaceMobileTab = "input" | "output" | "context";

type WorkspaceWritingLayoutProps = {
  header: React.ReactNode;
  input: React.ReactNode;
  output: React.ReactNode;
  context: React.ReactNode;
  drawerOpen: boolean;
  onDrawerOpenChange: (open: boolean) => void;
  bottomBar: React.ReactNode;
  className?: string;
};

export function WorkspaceWritingLayout({
  header,
  input,
  output,
  context,
  drawerOpen,
  onDrawerOpenChange,
  bottomBar,
  className,
}: WorkspaceWritingLayoutProps) {
  const splitRowRef = useRef<HTMLDivElement>(null);
  const [leftPct, setLeftPct] = useState(DEFAULT_LEFT_PCT);
  const [mobileTab, setMobileTab] = useState<WorkspaceMobileTab>("input");
  const [splitDragging, setSplitDragging] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(SPLIT_STORAGE_KEY);
      if (!raw) return;
      const n = Number(raw);
      if (!Number.isFinite(n)) return;
      setLeftPct(Math.min(MAX_LEFT_PCT, Math.max(MIN_LEFT_PCT, n)));
    } catch {
      /* ignore */
    }
  }, []);

  const persistSplit = useCallback((pct: number) => {
    try {
      localStorage.setItem(SPLIT_STORAGE_KEY, String(Math.round(pct)));
    } catch {
      /* ignore */
    }
  }, []);

  const onPointerMove = useCallback((e: PointerEvent) => {
    if (!splitRowRef.current) return;
    const rect = splitRowRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = (x / rect.width) * 100;
    setLeftPct(Math.min(MAX_LEFT_PCT, Math.max(MIN_LEFT_PCT, pct)));
  }, []);

  useEffect(() => {
    if (!splitDragging) return;
    const move = (e: PointerEvent) => onPointerMove(e);
    const end = () => {
      setSplitDragging(false);
      setLeftPct((p) => {
        persistSplit(p);
        return p;
      });
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end);
    window.addEventListener("pointercancel", end);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
      window.removeEventListener("pointercancel", end);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [splitDragging, onPointerMove, persistSplit]);

  const startDrag = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    setSplitDragging(true);
  }, []);

  return (
    <div
      className={cn(
        "flex min-h-0 flex-1 flex-col bg-background",
        "min-h-[calc(100dvh-3.5rem)] lg:min-h-[calc(100dvh-0px)]",
        className,
      )}
    >
      <div className="sticky top-0 z-30 shrink-0 border-b border-border bg-background/90 backdrop-blur-md">
        {header}
      </div>

      <div
        className="flex shrink-0 gap-1 border-b border-border bg-muted/30 p-1 lg:hidden"
        role="tablist"
        aria-label="Workspace"
      >
        {(
          [
            ["input", "Input"],
            ["output", "Output"],
            ["context", "Context"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={mobileTab === id}
            className={cn(
              "min-h-10 flex-1 rounded-lg px-3 text-[15px] font-medium transition-colors",
              mobileTab === id ? "bg-background text-foreground shadow-sm" : "text-muted-foreground",
            )}
            onClick={() => setMobileTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tablet: stacked */}
      <div className="hidden min-h-0 flex-1 flex-col md:flex lg:hidden">
        <div className="flex min-h-[42vh] shrink-0 flex-col border-b border-border bg-muted/15 dark:bg-white/[0.02]">
          {input}
        </div>
        <div className="relative min-h-0 flex-1 flex-col bg-background">
          <div className="absolute right-3 top-3 z-20">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-10 gap-2 rounded-xl border-border/80 bg-background/90 px-4 text-[14px] shadow-sm backdrop-blur"
              onClick={() => onDrawerOpenChange(true)}
            >
              <PanelRight className="size-4" aria-hidden />
              Context
            </Button>
          </div>
          {output}
        </div>
      </div>

      {/* Mobile: single active pane */}
      <div className="flex min-h-0 flex-1 flex-col md:hidden">
        {mobileTab === "input" ? (
          <div className="flex min-h-0 flex-1 flex-col bg-muted/15 dark:bg-white/[0.02]">{input}</div>
        ) : null}
        {mobileTab === "output" ? (
          <div className="flex min-h-0 flex-1 flex-col bg-background">{output}</div>
        ) : null}
        {mobileTab === "context" ? (
          <div className="flex min-h-0 flex-1 flex-col overflow-y-auto border-t border-border bg-muted/20 p-4">
            {context}
          </div>
        ) : null}
      </div>

      {/* Desktop: resizable split */}
      <div
        ref={splitRowRef}
        className="hidden min-h-0 flex-1 flex-row overflow-hidden lg:flex"
      >
        <div
          className="flex min-h-0 min-w-0 shrink-0 flex-col overflow-hidden border-r border-border bg-muted/15 dark:bg-white/[0.02]"
          style={{ flex: `0 0 ${leftPct}%` }}
        >
          {input}
        </div>
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize panels"
          className="relative z-10 w-1 shrink-0 cursor-col-resize touch-none select-none bg-border/80 hover:bg-primary/35"
          onPointerDown={startDrag}
        >
          <GripVertical
            className="pointer-events-none absolute left-1/2 top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 text-muted-foreground/80"
            aria-hidden
          />
        </div>
        <div className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background">
          <div className="absolute right-4 top-4 z-20">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className={cn(
                "h-10 gap-2 rounded-xl border-border/80 bg-background/90 px-4 text-[14px] shadow-sm backdrop-blur",
                drawerOpen && "border-primary/40 bg-primary/5",
              )}
              onClick={() => onDrawerOpenChange(!drawerOpen)}
            >
              <PanelRight className="size-4" aria-hidden />
              Context
            </Button>
          </div>
          {output}
        </div>
      </div>

      <div className="sticky bottom-0 z-40 shrink-0 border-t border-border bg-background/95 backdrop-blur-md supports-[backdrop-filter]:bg-background/80">
        {bottomBar}
      </div>

      {drawerOpen ? (
        <div
          className="fixed inset-0 z-50 hidden bg-black/40 md:block"
          aria-hidden
          onClick={() => onDrawerOpenChange(false)}
        />
      ) : null}
      <aside
        className={cn(
          "fixed inset-y-0 right-0 z-[60] flex w-[min(100%,420px)] max-md:hidden flex-col border-l border-border bg-background shadow-2xl transition-transform duration-200 ease-out supports-[backdrop-filter]:shadow-xl",
          drawerOpen ? "translate-x-0" : "translate-x-full pointer-events-none",
        )}
        aria-hidden={!drawerOpen}
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <p className="text-[13px] font-semibold tracking-tight text-foreground">Context</p>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-9 rounded-lg"
            onClick={() => onDrawerOpenChange(false)}
          >
            Close
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">{context}</div>
      </aside>
    </div>
  );
}
