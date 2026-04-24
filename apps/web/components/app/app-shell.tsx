"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { UserButton } from "@clerk/nextjs";
import { FilePlus2 } from "lucide-react";
import { APP_NAV, navItemIsActive } from "@/lib/nav-items";
import { ThemeToggle } from "@/components/bidforge/theme-toggle";
import { WorkspaceModeToggle } from "@/components/app/workspace-mode-toggle";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isProposalWorkspace = pathname === "/proposal";

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="hidden w-[248px] shrink-0 flex-col border-r border-border bg-sidebar md:flex">
        <div className="flex h-16 items-center px-5">
          <Link href="/dashboard" className="flex items-center gap-3">
            <span className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-violet-600 text-xs font-bold text-white shadow-md shadow-blue-500/25">
              BF
            </span>
            <span className="font-display text-base font-semibold tracking-[-0.02em]">
              BidForge
            </span>
          </Link>
        </div>
        <nav className="flex flex-1 flex-col gap-1 px-3 pb-4 pt-2">
          {APP_NAV.map(({ href, label, icon: Icon }) => {
            const active = navItemIsActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] font-medium transition-colors",
                  active
                    ? "bg-sidebar-accent text-sidebar-foreground shadow-sm"
                    : "text-muted-foreground hover:bg-sidebar-accent/70 hover:text-foreground",
                )}
              >
                <Icon className="size-[18px] shrink-0 opacity-90" aria-hidden />
                {label}
              </Link>
            );
          })}
        </nav>
      </aside>

      <div
        className={cn(
          "flex min-w-0 flex-1 flex-col",
          isProposalWorkspace && "min-h-0 max-h-[100dvh] overflow-hidden",
        )}
      >
        <header className="flex h-16 shrink-0 items-center justify-between gap-4 border-b border-border bg-background/85 px-4 backdrop-blur-md md:px-6">
          <div className="flex min-w-0 items-center gap-3 md:gap-4">
            <span className="font-display text-base font-semibold md:hidden">BidForge</span>
            {!isProposalWorkspace ? <WorkspaceModeToggle className="hidden sm:inline-flex" /> : null}
          </div>
          <div className="flex items-center gap-2">
            {!isProposalWorkspace ? <WorkspaceModeToggle className="sm:hidden" /> : null}
            <ThemeToggle />
            <Link
              href="/proposal"
              className={cn(
                buttonVariants({ size: "sm" }),
                "h-10 gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-4 text-[14px] font-semibold text-white shadow-sm hover:brightness-110",
              )}
            >
              <FilePlus2 className="size-4" aria-hidden />
              New proposal
            </Link>
            <UserButton
              appearance={{
                elements: {
                  userButtonAvatarBox: "size-9 ring-1 ring-border",
                },
              }}
            />
          </div>
        </header>

        <div className="border-b border-border px-3 py-3 md:hidden">
          <nav className="flex gap-2 overflow-x-auto pb-1">
            {APP_NAV.map(({ href, label }) => {
              const active = navItemIsActive(pathname, href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "whitespace-nowrap rounded-xl px-3 py-2 text-[14px] font-medium",
                    active ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>

        <main
          className={cn(
            "flex-1",
            isProposalWorkspace
              ? "flex min-h-0 flex-1 flex-col overflow-hidden px-0 py-0 md:py-0"
              : "px-4 py-8 md:px-6 md:py-10",
          )}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
