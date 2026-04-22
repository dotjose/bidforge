import { ProposalWorkspace } from "@/components/proposal/proposal-workspace";

type ProposalPageProps = {
  searchParams: Promise<{ run?: string }>;
};

export default async function ProposalPage({ searchParams }: ProposalPageProps) {
  const sp = await searchParams;
  const initialRunId = sp.run?.trim() || null;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <ProposalWorkspace initialRunId={initialRunId} />
    </div>
  );
}
