# BidForge Agents Architecture

BidForge routes each request through a small set of specialized roles. Together they turn a brief into a mode-appropriate proposal and a clear review—without exposing internal tooling names to customers.

## 1. Input Router Agent

Classifies raw text into **Enterprise RFP** vs **Freelance job** (Upwork, Freelancer, or informal job posts) and selects the cognitive path that follows.

## 2. Job Understanding Agent

Reads the post as **signals**, not instructions: extracts explicit asks, implicit needs, urgency, buyer sophistication, budget sensitivity, conversion triggers, and risk concerns that affect whether the client replies.

## 3. RAG Memory Agent

Retrieves indexed snippets: similar wins, methodology fragments, and **freelance win patterns** (hooks and short proof shapes). When nothing is indexed, the system may apply marked **synthetic starter seeds** so generation stays high-signal—never fake client names.

## 4. Freelance Hook Agent

Produces the **first screenful** of the bid: a tight hook, a trust signal, an honest relevance rating, and optional **A/B hook variants** so you can test angles quickly.

## 5. Proposal Generator Agent

Builds the final body using **mode-specific structure**. Freelance mode uses a conversion layout (hook → need → approach → proof → CTA), not RFP section titles. Enterprise mode uses structured long-form sections.

## 6. Verifier Agent

Scores the draft against the brief: enterprise runs emphasize compliance and completeness; freelance runs emphasize **reply likelihood**, hook strength, trust, and conciseness—and flag generic tone or “RFP voice” leaks.

## 7. CrossProposalDiffAgent

Contrasts the current proposal with the **last three rows** from `freelance_win_memory` (persisted high-scoring wins). Outputs **stronger_hooks**, **missing_signals**, **better_cta**, and **structure_optimization** lists for the Review tab. If the LLM step or memory read fails, the pipeline still completes with an empty diff (degraded observability only).

## 8. Critique Agent

Mode-aware polish notes; in freelance mode it may also emit an optional **top-1% style rewrite** for side-by-side comparison with your draft.
