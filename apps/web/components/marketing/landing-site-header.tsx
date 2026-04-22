"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Show, SignInButton, SignUpButton } from "@clerk/nextjs";
import { Layers, Menu, X } from "lucide-react";
import { ThemeToggle } from "@/components/bidforge/theme-toggle";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const nav = [
  { href: "#product", label: "Product" },
  { href: "#workflow", label: "Workflow" },
  { href: "#examples", label: "Examples" },
  { href: "#docs", label: "Docs" },
] as const;

function NavLinks({
  className,
  onNavigate,
}: {
  className?: string;
  onNavigate?: () => void;
}) {
  return (
    <ul className={cn("flex flex-col gap-1 lg:flex-row lg:items-center lg:gap-10", className)}>
      {nav.map((item) => (
        <li key={item.href}>
          <Link
            href={item.href}
            onClick={onNavigate}
            className="bf-landing-body block rounded-lg px-3 py-2.5 text-foreground/90 transition-colors hover:bg-muted hover:text-foreground lg:inline-block lg:px-0 lg:py-0 lg:hover:bg-transparent"
          >
            {item.label}
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function LandingSiteHeader() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <header className="sticky top-0 z-50 border-b border-border/80 bg-background/85 backdrop-blur-xl supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex h-16 max-w-[1240px] items-center gap-4 px-6 md:h-[72px] md:px-8 lg:px-10">
        <Link
          href="/"
          className="flex shrink-0 items-center gap-3 rounded-lg outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span className="flex size-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-violet-600 text-white shadow-md shadow-blue-500/20 ring-1 ring-black/5 dark:ring-white/10">
            <Layers className="size-[20px]" aria-hidden />
          </span>
          <span className="font-display text-lg font-bold tracking-[-0.03em] md:text-xl">BidForge</span>
        </Link>

        <nav
          className="absolute left-1/2 hidden -translate-x-1/2 lg:block"
          aria-label="Primary"
        >
          <NavLinks className="flex-row items-center gap-10" />
        </nav>

        <div className="ml-auto flex items-center gap-2 md:gap-3">
          <ThemeToggle />
          <Show when="signed-out">
            <SignInButton mode="modal">
              <Button
                variant="ghost"
                className="bf-landing-caption hidden h-10 px-3 text-foreground/80 hover:text-foreground sm:inline-flex"
              >
                Sign in
              </Button>
            </SignInButton>
            <SignUpButton mode="modal">
              <Button
                className={cn(
                  buttonVariants({ variant: "default" }),
                  "bf-cta-press hidden h-11 rounded-xl px-6 text-base font-semibold shadow-sm sm:inline-flex",
                )}
              >
                Sign up
              </Button>
            </SignUpButton>
          </Show>
          <Show when="signed-in">
            <Link
              href="/dashboard"
              className={cn(
                buttonVariants({ variant: "default" }),
                "bf-cta-press hidden h-11 rounded-xl px-6 text-base font-semibold sm:inline-flex",
              )}
            >
              Dashboard
            </Link>
          </Show>

          <button
            type="button"
            className="inline-flex size-10 items-center justify-center rounded-xl border border-border bg-background text-foreground lg:hidden"
            aria-expanded={open}
            aria-controls="mobile-nav"
            onClick={() => setOpen((v) => !v)}
          >
            <span className="sr-only">{open ? "Close menu" : "Open menu"}</span>
            {open ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
      </div>

      {open ? (
        <div className="fixed inset-0 top-16 z-40 lg:hidden" id="mobile-nav">
          <button
            type="button"
            className="absolute inset-0 bg-black/40 dark:bg-black/60"
            aria-label="Close menu"
            onClick={() => setOpen(false)}
          />
          <div className="relative border-b border-border bg-background px-6 py-6 shadow-xl">
            <NavLinks onNavigate={() => setOpen(false)} />
            <div className="mt-6 flex flex-col gap-3 border-t border-border pt-6">
              <Show when="signed-out">
                <SignInButton mode="modal">
                  <Button variant="outline" className="h-12 w-full rounded-xl text-base" onClick={() => setOpen(false)}>
                    Sign in
                  </Button>
                </SignInButton>
                <SignUpButton mode="modal">
                  <Button className="bf-cta-press h-12 w-full rounded-xl text-base font-semibold" onClick={() => setOpen(false)}>
                    Sign up
                  </Button>
                </SignUpButton>
              </Show>
              <Show when="signed-in">
                <Link
                  href="/dashboard"
                  className={cn(buttonVariants({ variant: "default" }), "h-12 w-full rounded-xl text-base font-semibold")}
                  onClick={() => setOpen(false)}
                >
                  Dashboard
                </Link>
              </Show>
            </div>
          </div>
        </div>
      ) : null}
    </header>
  );
}
