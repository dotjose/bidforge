import Link from "next/link";
import { CompanyProfileForm } from "@/components/profile/company-profile-form";
import { BfContainer } from "@/components/bidforge/bf-container";
import { WorkspaceRetrievalForm } from "@/components/settings/workspace-retrieval-form";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";

function SettingsTabs() {
  return (
    <nav className="flex flex-wrap gap-2 border-b border-border pb-4">
      <Link
        href="/settings/workspace"
        className={cn(
          buttonVariants({ variant: "secondary", size: "sm" }),
          "rounded-full px-5",
        )}
      >
        Workspace
      </Link>
      <Link
        href="/settings/personal"
        className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "rounded-full px-5")}
      >
        Personal
      </Link>
    </nav>
  );
}

export default function WorkspaceSettingsPage() {
  return (
    <BfContainer>
      <div className="max-w-3xl">
        <h1 className="font-display text-3xl font-semibold tracking-[-0.03em] text-foreground">
          Workspace settings
        </h1>
        <p className="mt-4 text-base leading-relaxed text-muted-foreground">
          Company context and retrieval preferences apply to this account&apos;s proposal runs.
        </p>
        <div className="mt-10">
          <SettingsTabs />
        </div>

        <section className="mt-12">
          <h2 className="font-display text-lg font-semibold text-foreground">Company profile</h2>
          <p className="mt-2 text-base text-muted-foreground">
            Keeps drafts aligned with how you position your firm on bids and job posts.
          </p>
          <div className="mt-8">
            <CompanyProfileForm />
          </div>
        </section>

        <section className="mt-16 pb-8">
          <h2 className="font-display text-lg font-semibold text-foreground">Retrieval &amp; memory</h2>
          <p className="mt-2 text-base text-muted-foreground">
            Controls which indexed libraries the pipeline may query for this workspace. When retrieval is off,
            drafts still complete using the brief alone.
          </p>
          <div className="mt-8 rounded-2xl border border-border bg-card p-8 shadow-sm">
            <WorkspaceRetrievalForm />
          </div>
        </section>
      </div>
    </BfContainer>
  );
}
