"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { BidForgeApiError, BidForgeClient } from "@bidforge/web-sdk";
import { useProposalStore, type BrainMode } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/bidforge/theme-toggle";
import { cn } from "@/lib/utils";

const fieldClass =
  "mt-2 w-full min-h-[120px] resize-y rounded-xl border border-border bg-background px-4 py-3 text-base leading-relaxed text-foreground shadow-inner outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring";

export function PersonalPreferencesForm() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const client = useMemo(() => new BidForgeClient({ getToken: () => getToken() }), [getToken]);
  const brainMode = useProposalStore((s) => s.brainMode);
  const setBrainMode = useProposalStore((s) => s.setBrainMode);
  const [writingStyle, setWritingStyle] = useState("");
  const [tonePreferences, setTonePreferences] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    if (!isLoaded || !isSignedIn) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const row = await client.getWorkspaceSettings();
      setWritingStyle(row.writing_style ?? "");
      setTonePreferences(row.tone ?? "");
      const pm = row.proposal_mode;
      if (pm === "auto" || pm === "enterprise" || pm === "freelance") {
        setBrainMode(pm);
      }
    } catch (e) {
      setError(e instanceof BidForgeApiError ? e.message : (e as Error).message || "Could not load preferences.");
    } finally {
      setLoading(false);
    }
  }, [client, isLoaded, isSignedIn, setBrainMode]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    if (!isSignedIn) return;
    setSaving(true);
    setError(null);
    try {
      await client.updateWorkspaceSettings({
        tone: tonePreferences,
        writing_style: writingStyle,
        proposal_mode: brainMode,
      });
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err instanceof BidForgeApiError ? err.message : (err as Error).message || "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  if (!isLoaded) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  if (!isSignedIn) {
    return <p className="text-sm text-muted-foreground">Sign in to manage preferences.</p>;
  }

  return (
    <form onSubmit={onSave} className="space-y-12">
      {error ? (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      <section className="rounded-2xl border border-border bg-card p-8 shadow-sm">
        <h2 className="font-display text-lg font-semibold text-foreground">Appearance</h2>
        <p className="mt-2 text-base text-muted-foreground">Light, dark, or match your system.</p>
        <div className="mt-6 flex items-center gap-4">
          <span className="text-base text-muted-foreground">Theme</span>
          <ThemeToggle />
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-card p-8 shadow-sm">
        <h2 className="font-display text-lg font-semibold text-foreground">Default proposal mode</h2>
        <p className="mt-2 text-base text-muted-foreground">
          Stored with your workspace. Auto lets BidForge infer enterprise vs freelance from the brief.
        </p>
        <div className="mt-6 flex flex-wrap gap-2">
          {(
            [
              ["enterprise", "Enterprise"],
              ["freelance", "Freelance win"],
              ["auto", "Auto-detect"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setBrainMode(id as BrainMode)}
              className={cn(
                "rounded-full border px-4 py-2 text-[15px] font-medium transition-colors",
                brainMode === id
                  ? "border-blue-500/60 bg-blue-500/10 text-foreground"
                  : "border-border bg-muted/30 text-muted-foreground hover:text-foreground",
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-card p-8 shadow-sm">
        <h2 className="font-display text-lg font-semibold text-foreground">Writing style</h2>
        <p className="mt-2 text-base text-muted-foreground">
          Applied on every run via workspace settings (merged before the five-node proposal graph starts).
        </p>
        {loading ? (
          <p className="mt-4 text-sm text-muted-foreground">Loading saved style…</p>
        ) : (
          <textarea
            value={writingStyle}
            onChange={(e) => setWritingStyle(e.target.value)}
            placeholder="Direct and confident; short paragraphs; avoid buzzwords…"
            className={fieldClass}
            disabled={saving}
          />
        )}
      </section>

      <section className="rounded-2xl border border-border bg-card p-8 shadow-sm">
        <h2 className="font-display text-lg font-semibold text-foreground">Tone preferences</h2>
        <p className="mt-2 text-base text-muted-foreground">How replies should read by default.</p>
        {loading ? (
          <p className="mt-4 text-sm text-muted-foreground">Loading saved tone…</p>
        ) : (
          <textarea
            value={tonePreferences}
            onChange={(e) => setTonePreferences(e.target.value)}
            placeholder="Warm but professional; cite outcomes; one clear CTA…"
            className={fieldClass}
            disabled={saving}
          />
        )}
      </section>

      <Button type="submit" disabled={saving || loading} className="h-11 rounded-xl px-8 text-[15px] font-semibold">
        {saving ? "Saving…" : saved ? "Saved" : "Save to workspace"}
      </Button>
    </form>
  );
}
