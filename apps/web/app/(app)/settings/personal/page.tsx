import Link from "next/link";
import { PersonalPreferencesForm } from "@/components/settings/personal-preferences-form";
import { BfContainer } from "@/components/bidforge/bf-container";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function SettingsTabs() {
  return (
    <nav className="flex flex-wrap gap-2 border-b border-border pb-4">
      <Link
        href="/settings/workspace"
        className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "rounded-full px-5")}
      >
        Workspace
      </Link>
      <Link
        href="/settings/personal"
        className={cn(
          buttonVariants({ variant: "secondary", size: "sm" }),
          "rounded-full px-5",
        )}
      >
        Personal
      </Link>
    </nav>
  );
}

export default function PersonalSettingsPage() {
  return (
    <BfContainer>
      <div className="max-w-3xl">
        <h1 className="font-display text-3xl font-semibold tracking-[-0.03em] text-foreground">
          Personal settings
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          How you like to write, sound, and work—only affects your experience, not the whole workspace.
        </p>
        <div className="mt-10">
          <SettingsTabs />
        </div>
        <div className="mt-12">
          <PersonalPreferencesForm />
        </div>
      </div>
    </BfContainer>
  );
}
