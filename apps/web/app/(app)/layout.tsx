import { AppShell } from "@/components/app/app-shell";

export default function AppShellLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppShell>{children}</AppShell>;
}
