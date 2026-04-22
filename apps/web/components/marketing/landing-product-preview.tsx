"use client";

import { LandingWorkspaceMock } from "@/components/marketing/landing-workspace-mock";

export function LandingProductPreview() {
  return (
    <LandingWorkspaceMock
      id="workspace-demo"
      density="comfortable"
      animateInView
      showFrameBranding
    />
  );
}
