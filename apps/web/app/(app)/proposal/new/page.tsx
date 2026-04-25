import { Suspense } from "react";
import { ProposalWorkspace } from "@/components/proposal/proposal-workspace";

export default function NewProposalPage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <Suspense fallback={null}>
        <ProposalWorkspace initialRunId={null} mode="new" />
      </Suspense>
    </div>
  );
}

