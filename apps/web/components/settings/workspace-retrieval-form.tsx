"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { BidForgeApiError, BidForgeClient, type WorkspaceSettingsResponse } from "@bidforge/web-sdk";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function SwitchRow(props: {
  id: string;
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-col gap-2 border-b border-border py-4 last:border-b-0 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <label htmlFor={props.id} className="text-[15px] font-medium text-foreground">
          {props.label}
        </label>
        <p className="mt-1 text-sm text-muted-foreground">{props.description}</p>
      </div>
      <button
        type="button"
        id={props.id}
        role="switch"
        aria-checked={props.checked}
        disabled={props.disabled}
        onClick={() => props.onChange(!props.checked)}
        className={cn(
          "relative h-8 w-14 shrink-0 rounded-full border transition-colors",
          props.checked ? "border-blue-500/50 bg-blue-500/20" : "border-border bg-muted/40",
          props.disabled && "cursor-not-allowed opacity-50",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 size-7 rounded-full bg-background shadow transition-transform",
            props.checked ? "left-6" : "left-0.5",
          )}
        />
      </button>
    </div>
  );
}

export function WorkspaceRetrievalForm() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const client = useMemo(() => new BidForgeClient({ getToken: () => getToken() }), [getToken]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);
  const [ragEnabled, setRagEnabled] = useState(true);
  const [enterpriseCs, setEnterpriseCs] = useState(true);
  const [freelanceMem, setFreelanceMem] = useState(true);

  const load = useCallback(async () => {
    if (!isLoaded || !isSignedIn) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const s: WorkspaceSettingsResponse = await client.getWorkspaceSettings();
      const rc = s.rag_config ?? {};
      setRagEnabled(rc.enabled !== false);
      setEnterpriseCs(rc.enterprise_case_studies !== false);
      setFreelanceMem(rc.freelance_win_memory !== false);
    } catch (e) {
      setError(e instanceof BidForgeApiError ? e.message : (e as Error).message || "Could not load settings.");
    } finally {
      setLoading(false);
    }
  }, [client, isLoaded, isSignedIn]);

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
        rag_config: {
          enabled: ragEnabled,
          enterprise_case_studies: enterpriseCs,
          freelance_win_memory: freelanceMem,
        },
      });
      setSavedFlash(true);
      window.setTimeout(() => setSavedFlash(false), 2000);
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
    return <p className="text-sm text-muted-foreground">Sign in to configure retrieval for your workspace.</p>;
  }

  return (
    <form onSubmit={onSave} className="space-y-2">
      {loading ? (
        <p className="text-sm text-muted-foreground">Loading retrieval preferences…</p>
      ) : (
        <>
          {error ? (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          ) : null}
          <SwitchRow
            id="rag-enabled"
            label="Retrieval on"
            description="When off, proposals run without indexed memory (still completes)."
            checked={ragEnabled}
            onChange={setRagEnabled}
            disabled={saving}
          />
          <SwitchRow
            id="rag-enterprise"
            label="Enterprise case studies"
            description="Use structured RFP wins and methodology from your library when the job looks like an enterprise bid."
            checked={enterpriseCs}
            onChange={setEnterpriseCs}
            disabled={saving || !ragEnabled}
          />
          <SwitchRow
            id="rag-freelance"
            label="Freelance win memory"
            description="Use Upwork-style hooks and reply patterns when the job looks like a marketplace post."
            checked={freelanceMem}
            onChange={setFreelanceMem}
            disabled={saving || !ragEnabled}
          />
        </>
      )}
      <div className="pt-4">
        <Button type="submit" disabled={saving || loading} className="h-10 rounded-xl px-6 text-[14px] font-semibold">
          {saving ? "Saving…" : savedFlash ? "Saved" : "Save retrieval settings"}
        </Button>
      </div>
    </form>
  );
}
