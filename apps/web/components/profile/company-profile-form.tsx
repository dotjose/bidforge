"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { BidForgeApiError, BidForgeClient, type WorkspaceSettingsResponse } from "@bidforge/web-sdk";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Profile = {
  companyName: string;
  services: string;
  strengths: string;
  methodology: string;
};

const empty: Profile = {
  companyName: "",
  services: "",
  strengths: "",
  methodology: "",
};

const field =
  "w-full rounded-xl border border-border bg-background px-4 py-3 text-[14px] text-foreground shadow-inner outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring";

function fromRow(row: WorkspaceSettingsResponse): Profile {
  const cp = row.company_profile ?? {};
  return {
    companyName: typeof cp.company_name === "string" ? cp.company_name : "",
    services: typeof cp.services === "string" ? cp.services : "",
    strengths: typeof cp.strengths === "string" ? cp.strengths : "",
    methodology: typeof cp.methodology === "string" ? cp.methodology : "",
  };
}

export function CompanyProfileForm() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const client = useMemo(() => new BidForgeClient({ getToken: () => getToken() }), [getToken]);
  const [values, setValues] = useState<Profile>(empty);
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
      setValues(fromRow(row));
    } catch (e) {
      setError(e instanceof BidForgeApiError ? e.message : (e as Error).message || "Could not load profile.");
    } finally {
      setLoading(false);
    }
  }, [client, isLoaded, isSignedIn]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isSignedIn) return;
    setSaving(true);
    setError(null);
    try {
      await client.updateWorkspaceSettings({
        company_profile: {
          company_name: values.companyName.trim(),
          services: values.services.trim(),
          strengths: values.strengths.trim(),
          methodology: values.methodology.trim(),
        },
      });
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2200);
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
    return <p className="text-sm text-muted-foreground">Sign in to edit your company profile.</p>;
  }

  return (
    <form onSubmit={onSubmit} className="space-y-8">
      {loading ? <p className="text-sm text-muted-foreground">Loading company profile…</p> : null}
      {error ? (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      ) : null}
      <div className="space-y-2">
        <label htmlFor="companyName" className="text-[13px] font-medium text-zinc-300">
          Company name
        </label>
        <input
          id="companyName"
          value={values.companyName}
          onChange={(e) => setValues((v) => ({ ...v, companyName: e.target.value }))}
          className={field}
          disabled={loading || saving}
        />
      </div>
      <div className="space-y-2">
        <label htmlFor="services" className="text-[13px] font-medium text-zinc-300">
          What you deliver
        </label>
        <textarea
          id="services"
          rows={4}
          value={values.services}
          onChange={(e) => setValues((v) => ({ ...v, services: e.target.value }))}
          placeholder="Services, industries, and typical engagements…"
          className={cn(field, "min-h-[120px] resize-y")}
          disabled={loading || saving}
        />
      </div>
      <div className="space-y-2">
        <label htmlFor="strengths" className="text-[13px] font-medium text-zinc-300">
          Proof points
        </label>
        <textarea
          id="strengths"
          rows={4}
          value={values.strengths}
          onChange={(e) => setValues((v) => ({ ...v, strengths: e.target.value }))}
          placeholder="Differentiators, outcomes, credentials your reviewers expect…"
          className={cn(field, "min-h-[120px] resize-y")}
          disabled={loading || saving}
        />
      </div>
      <div className="space-y-2">
        <label htmlFor="methodology" className="text-[13px] font-medium text-zinc-300">
          How you work
        </label>
        <textarea
          id="methodology"
          rows={4}
          value={values.methodology}
          onChange={(e) => setValues((v) => ({ ...v, methodology: e.target.value }))}
          placeholder="Phases, governance, how you de-risk delivery…"
          className={cn(field, "min-h-[120px] resize-y")}
          disabled={loading || saving}
        />
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="submit"
          disabled={loading || saving}
          className="h-10 rounded-xl bg-gradient-to-r from-blue-500 to-violet-600 px-5 text-[14px] font-semibold text-white hover:brightness-110"
        >
          {saving ? "Saving…" : "Save"}
        </Button>
        {saved ? <span className="text-[13px] text-emerald-400/90">Saved.</span> : null}
      </div>
    </form>
  );
}
