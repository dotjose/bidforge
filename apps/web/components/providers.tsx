"use client";

import { ClerkProvider } from "@clerk/nextjs";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BidForgeAppToaster } from "@/components/bidforge-app-toaster";
import { AppThemeProvider } from "@/components/theme-provider";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 60 * 1000 },
        },
      }),
  );

  return (
    <ClerkProvider>
      <AppThemeProvider
        attribute="class"
        defaultTheme="dark"
        enableSystem
        storageKey="bidforge-theme"
        disableTransitionOnChange
      >
        <QueryClientProvider client={queryClient}>
          {children}
          <BidForgeAppToaster />
        </QueryClientProvider>
      </AppThemeProvider>
    </ClerkProvider>
  );
}
