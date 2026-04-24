"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Toaster } from "sonner";

export function BidForgeAppToaster() {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;
  return (
    <Toaster
      position="top-center"
      richColors
      closeButton
      duration={4500}
      theme={resolvedTheme === "dark" ? "dark" : "light"}
    />
  );
}
