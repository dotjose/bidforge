"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { GripVertical } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

/** Focus mode: wide brief column (~60–70%), proposal on the right. */
const STORAGE_LEFT_PCT = "bf-editor-focus-input-pct";
const DEFAULT_LEFT_PCT = 64;
const MIN_LEFT_PCT = 55;
const MAX_LEFT_PCT = 72;

export type WorkspaceEditorTab = "input" | "proposal";

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
  const leftRef = useRef(DEFAULT_LEFT_PCT);
  const [leftPct, setLeftPct] = useState(DEFAULT_LEFT_PCT);
  const [mobileTab, setMobileTab] = useState<WorkspaceEditorTab>("input");
  const [splitDragging, setSplitDragging] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_LEFT_PCT);
      const n = Number(raw);
      if (!Number.isFinite(n)) return;
      setLeftPct(Math.min(MAX_LEFT_PCT, Math.max(MIN_LEFT_PCT, n)));
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    leftRef.current = leftPct;
  }, [leftPct]);

  const persistLeft = useCallback((pct: number) => {
    try {
      localStorage.setItem(STORAGE_LEFT_PCT, String(Math.round(pct)));
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
      persistLeft(leftRef.current);
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
  }, [splitDragging, onPointerMove, persistLeft]);

  const startDrag = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    setSplitDragging(true);
  }, []);

  return (
    <div
      className={cn(
        "flex min-h-0 flex-1 flex-col bg-background",
        "min-h-[calc(100dvh-3.5rem)] md:min-h-[calc(100dvh-0px)]",
        className,
      )}
    >
      <div className="sticky top-0 z-30 shrink-0 border-b border-border bg-background/90 backdrop-blur-md">
        {header}
      </div>

      {/* Mobile: stack Input → Proposal (context = drawer only) */}
      <div className="flex min-h-0 flex-1 flex-col md:hidden">
        <div
          className="flex shrink-0 gap-1 border-b border-border bg-muted/30 p-1"
          role="tablist"
          aria-label="Workspace"
        >
          {(
            [
              ["input", "Brief"],
              ["proposal", "Proposal"],
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
        {mobileTab === "input" ? (
          <div className="flex min-h-0 flex-1 flex-col bg-muted/15 dark:bg-white/[0.02]">{input}</div>
        ) : (
          <div className="relative flex min-h-0 flex-1 flex-col bg-background">{output}</div>
        )}
      </div>

      {/* Tablet + desktop: two panes — brief | proposal (no third column) */}
      <div
        ref={splitRowRef}
        className="hidden min-h-0 flex-1 flex-row overflow-hidden md:flex"
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
          aria-label="Resize brief panel"
          className="relative z-10 w-1 shrink-0 cursor-col-resize touch-none select-none bg-border/80 hover:bg-primary/35"
          onPointerDown={startDrag}
        >
          <GripVertical
            className="pointer-events-none absolute left-1/2 top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 text-muted-foreground/80"
            aria-hidden
          />
        </div>
        <div className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background">
          {output}
        </div>
      </div>

      <div className="sticky bottom-0 z-40 shrink-0 border-t border-border bg-background/95 backdrop-blur-md supports-[backdrop-filter]:bg-background/80">
        {bottomBar}
      </div>

      {drawerOpen ? (
        <div
          className="fixed inset-0 z-50 bg-black/40"
          role="presentation"
          aria-hidden
          onClick={() => onDrawerOpenChange(false)}
        />
      ) : null}

      <aside
        className={cn(
          "fixed inset-y-0 right-0 z-[60] flex w-[min(100vw,400px)] min-w-[320px] max-w-[400px] flex-col border-l border-border bg-background shadow-2xl transition-transform duration-200 ease-out supports-[backdrop-filter]:shadow-xl",
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
