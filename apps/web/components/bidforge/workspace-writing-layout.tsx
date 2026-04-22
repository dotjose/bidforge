"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { GripVertical, PanelRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const STORAGE_S1 = "bf-workspace-split1";
const STORAGE_S2 = "bf-workspace-split2";
/** Column 1 end / column 2 end as % of row width (col3 = 100 - s2). Defaults ≈ 30 / 50 / 20. */
const DEFAULT_S1 = 30;
const DEFAULT_S2 = 80;
const MIN_S1 = 22;
const MIN_MID = 28;
const MIN_RIGHT = 15;

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

type DragMode = "none" | "split1" | "split2";

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
  const s1Ref = useRef(DEFAULT_S1);
  const s2Ref = useRef(DEFAULT_S2);
  const [s1, setS1] = useState(DEFAULT_S1);
  const [s2, setS2] = useState(DEFAULT_S2);
  const [mobileTab, setMobileTab] = useState<WorkspaceMobileTab>("input");
  const [dragMode, setDragMode] = useState<DragMode>("none");

  useEffect(() => {
    try {
      const a = Number(localStorage.getItem(STORAGE_S1));
      const b = Number(localStorage.getItem(STORAGE_S2));
      if (Number.isFinite(a) && Number.isFinite(b) && b > a + MIN_MID && b < 100 - MIN_RIGHT) {
        setS1(Math.min(48, Math.max(MIN_S1, a)));
        setS2(Math.min(100 - MIN_RIGHT, Math.max(a + MIN_MID, b)));
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    s1Ref.current = s1;
    s2Ref.current = s2;
  }, [s1, s2]);

  const persistSplits = useCallback((a: number, b: number) => {
    try {
      localStorage.setItem(STORAGE_S1, String(Math.round(a)));
      localStorage.setItem(STORAGE_S2, String(Math.round(b)));
    } catch {
      /* ignore */
    }
  }, []);

  const onPointerMove = useCallback(
    (e: PointerEvent) => {
      if (!splitRowRef.current || dragMode === "none") return;
      const rect = splitRowRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const pct = (x / rect.width) * 100;
      if (dragMode === "split1") {
        setS1(Math.min(s2Ref.current - MIN_MID, Math.max(MIN_S1, pct)));
      } else if (dragMode === "split2") {
        setS2(Math.min(100 - MIN_RIGHT, Math.max(s1Ref.current + MIN_MID, pct)));
      }
    },
    [dragMode],
  );

  useEffect(() => {
    if (dragMode === "none") return;
    const move = (e: PointerEvent) => onPointerMove(e);
    const end = () => {
      setDragMode("none");
      persistSplits(s1Ref.current, s2Ref.current);
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
  }, [dragMode, onPointerMove, persistSplits]);

  const startDrag1 = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    setDragMode("split1");
  }, []);

  const startDrag2 = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    setDragMode("split2");
  }, []);

  const w1 = s1;
  const w2 = Math.max(MIN_MID, s2 - s1);
  const w3 = Math.max(MIN_RIGHT, 100 - s2);

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
            ["output", "Proposal"],
            ["context", "Memory"],
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

      {/* Tablet: stacked + context drawer */}
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
              Memory / issues
            </Button>
          </div>
          {output}
        </div>
      </div>

      {/* Mobile */}
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

      {/* Desktop: 3 columns — input / proposal / memory */}
      <div ref={splitRowRef} className="hidden min-h-0 flex-1 flex-row overflow-hidden lg:flex">
        <div
          className="flex min-h-0 min-w-0 shrink-0 flex-col overflow-hidden border-r border-border bg-muted/15 dark:bg-white/[0.02]"
          style={{ flex: `0 0 ${w1}%` }}
        >
          {input}
        </div>
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize input column"
          className="relative z-10 w-1 shrink-0 cursor-col-resize touch-none select-none bg-border/80 hover:bg-primary/35"
          onPointerDown={startDrag1}
        >
          <GripVertical
            className="pointer-events-none absolute left-1/2 top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 text-muted-foreground/80"
            aria-hidden
          />
        </div>
        <div
          className="flex min-h-0 min-w-0 shrink-0 flex-col overflow-hidden border-r border-border bg-background"
          style={{ flex: `0 0 ${w2}%` }}
        >
          {output}
        </div>
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize proposal column"
          className="relative z-10 w-1 shrink-0 cursor-col-resize touch-none select-none bg-border/80 hover:bg-primary/35"
          onPointerDown={startDrag2}
        >
          <GripVertical
            className="pointer-events-none absolute left-1/2 top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 text-muted-foreground/80"
            aria-hidden
          />
        </div>
        <div
          className="flex min-h-0 min-w-0 flex-col overflow-y-auto border-border bg-muted/10 px-4 py-6 dark:bg-white/[0.02]"
          style={{ flex: `0 0 ${w3}%`, minWidth: `${MIN_RIGHT}%` }}
        >
          {context}
        </div>
      </div>

      <div className="sticky bottom-0 z-40 shrink-0 border-t border-border bg-background/95 backdrop-blur-md supports-[backdrop-filter]:bg-background/80">
        {bottomBar}
      </div>

      {drawerOpen ? (
        <div
          className="fixed inset-0 z-50 hidden bg-black/40 md:block lg:hidden"
          aria-hidden
          onClick={() => onDrawerOpenChange(false)}
        />
      ) : null}
      <aside
        className={cn(
          "fixed inset-y-0 right-0 z-[60] hidden w-[min(100%,420px)] flex-col border-l border-border bg-background shadow-2xl transition-transform duration-200 ease-out supports-[backdrop-filter]:shadow-xl md:flex lg:hidden",
          drawerOpen ? "translate-x-0" : "translate-x-full pointer-events-none",
        )}
        aria-hidden={!drawerOpen}
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <p className="text-[13px] font-semibold tracking-tight text-foreground">Memory / issues</p>
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
