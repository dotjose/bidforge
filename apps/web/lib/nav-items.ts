import {
  Brain,
  FilePlus2,
  Files,
  LayoutDashboard,
  Lightbulb,
  Settings2,
} from "lucide-react";

export const APP_NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/proposal", label: "New Proposal", icon: FilePlus2 },
  { href: "/drafts", label: "Drafts", icon: Files },
  { href: "/memory", label: "Memory", icon: Brain },
  { href: "/insights", label: "Insights", icon: Lightbulb },
  { href: "/settings/workspace", label: "Settings", icon: Settings2 },
] as const;

export function navItemIsActive(pathname: string, href: string): boolean {
  if (href === "/dashboard") return pathname === "/dashboard";
  if (href === "/settings/workspace") {
    return pathname.startsWith("/settings");
  }
  if (href === "/proposal") {
    return pathname === "/proposal" || pathname.startsWith("/proposal/");
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}
