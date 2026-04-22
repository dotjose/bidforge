"use client";

import { BidForgeClient, BidForgeApiError, type ProposalRunResponse } from "@bidforge/web-sdk";
import { useAuth } from "@clerk/nextjs";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export type ProposalRunState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: ProposalRunResponse }
  | { status: "error"; message: string; code?: string; traceId?: string };

const SUBMIT_DEBOUNCE_MS = 400;
const MIN_SUBMIT_INTERVAL_MS = 900;

export function useProposalRun() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [state, setState] = useState<ProposalRunState>({ status: "idle" });
  const [rfpMaxChars, setRfpMaxChars] = useState(120_000);
  const client = useMemo(
    () =>
      new BidForgeClient({
        getToken: () => getToken(),
      }),
    [getToken],
  );

  const busyRef = useRef(false);
  const lastRunAt = useRef(0);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const v = await client.getVersion();
        if (!cancelled && typeof v.rfp_max_chars === "number") {
          setRfpMaxChars(v.rfp_max_chars);
        }
      } catch {
        /* keep default */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [client]);

  const reset = useCallback(() => {
    setState({ status: "idle" });
  }, []);

  const runNow = useCallback(
    async (
      rfp: string,
      pipelineMode: "auto" | "enterprise" | "freelance" = "auto",
      draftIntensity: "balanced" | "strong" | "weak" = "balanced",
    ) => {
      if (!isLoaded) {
        setState({
          status: "error",
          message: "Auth is still loading.",
          code: "UNAUTHORIZED",
        });
        return;
      }
      if (!isSignedIn) {
        setState({
          status: "error",
          message: "You must be signed in to generate a proposal.",
          code: "UNAUTHORIZED",
        });
        return;
      }
      const trimmed = rfp.trim();
      if (!trimmed.length) {
        setState({
          status: "error",
          message: "Brief cannot be empty.",
          code: "VALIDATION_ERROR",
        });
        return;
      }
      if (trimmed.length > rfpMaxChars) {
        setState({
          status: "error",
          message: `Brief exceeds maximum length (${rfpMaxChars} characters).`,
          code: "VALIDATION_ERROR",
        });
        return;
      }

      const now = Date.now();
      if (busyRef.current) return;
      if (now - lastRunAt.current < MIN_SUBMIT_INTERVAL_MS) return;

      busyRef.current = true;
      lastRunAt.current = now;
      setState({ status: "loading" });

      try {
        const data = await client.runProposal({
          rfp: trimmed,
          pipelineMode,
          draftIntensity,
        });
        setState({ status: "success", data });
      } catch (e) {
        if (e instanceof BidForgeApiError) {
          setState({
            status: "error",
            message: e.message,
            code: e.code,
            traceId: e.traceId,
          });
        } else {
          setState({
            status: "error",
            message: (e as Error).message || "Unexpected error",
            code: "INTERNAL_ERROR",
          });
        }
      } finally {
        busyRef.current = false;
      }
    },
    [client, isLoaded, isSignedIn, rfpMaxChars],
  );

  /** Debounced trailing submit — coalesces rapid clicks; still guarded by busy + min interval. */
  const runDebounced = useCallback(
    (
      rfp: string,
      pipelineMode: "auto" | "enterprise" | "freelance" = "auto",
      draftIntensity: "balanced" | "strong" | "weak" = "balanced",
    ) => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
      debounceTimer.current = setTimeout(() => {
        debounceTimer.current = undefined;
        void runNow(rfp, pipelineMode, draftIntensity);
      }, SUBMIT_DEBOUNCE_MS);
    },
    [runNow],
  );

  useEffect(
    () => () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    },
    [],
  );

  return {
    state,
    runDebounced,
    runNow,
    reset,
    rfpMaxChars,
    isAuthReady: isLoaded,
    isSignedIn: Boolean(isSignedIn),
    apiClient: client,
  };
}
