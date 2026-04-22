# BidForge

BidForge helps you turn a client brief—whether a formal RFP or a short job post—into a structured proposal you can edit, review, and ship with confidence.

## What it does

You paste or import your brief. BidForge organizes the requirements, drafts a response in the right format, highlights risks and gaps, and suggests a timeline when the brief supports it. Past wins and reusable language can strengthen future drafts when you choose to save them.

## Modes

- **Enterprise** — Long-form, sectioned proposals suited to formal bids and multi-stakeholder reviews.
- **Freelance win** — Concise replies for marketplaces and direct outreach, with emphasis on a strong hook and reply-oriented signals.

Switch modes from the app header or set your default under **Settings → Personal**.

## How the workflow feels

1. **Dashboard** — Start a new proposal or import text; your list stays empty until real runs exist—no demo listings.
2. **New proposal** — Large brief area on the left; **Draft**, **Review**, **Timeline**, and **Insights** on the right, all driven by your latest generation.
3. **Drafts** — Reserved for saved history as your account grows.
4. **Memory** — Describes how your intelligence library will surface; per-run retrieval appears under **Insights** on the proposal screen.
5. **Insights** — Reserved for cross-proposal analytics as they become available.

## Who it is for

Consultancies, agencies, and solo operators who respond to formal RFPs and to short-form client opportunities—and want one calm workspace instead of scattered docs.

## Getting started

### Web app

```bash
cp apps/web/.env.example apps/web/.env.local
# Add Clerk keys from https://dashboard.clerk.com

npm install
npm run dev
```

Open http://localhost:3000, sign in, and use **New proposal** from the sidebar.

### API (optional, for full generation)

```bash
cp api/.env.example api/.env
cd api && uv sync && uv run uvicorn app.main:app --reload --port 8000
```

Configure environment variables as described in `apps/web/.env.example` and `api/.env.example`.

### Vercel

Use the **repository root** as the Vercel project root (never `apps/api` — that path does not exist). Root `vercel.json` runs `npm install`, installs **`uv`**, runs **`uv python install 3.12`** (the Node build image defaults to Python 3.9; workspace packages require **≥3.11**), then **`uv pip install --system --break-system-packages --python 3.12 -r requirements.txt`** (root file with `./packages/…` editables), then `npm run build` (Turbo builds `apps/web`). `.python-version` pins **3.12** for the Python runtime. Enable **Include files outside the root** if your preset scopes the checkout.

## Monorepo layout

- `apps/web` — Next.js product UI
- `api/` — FastAPI service (Python serverless + local `uvicorn`)
- `packages/web-sdk` — Typed client used by the browser
- `packages/agents`, `packages/prompts`, `packages/schemas`, `packages/shared` — Server-side generation assets
- `infra/` — Database and observability configuration for operators

## Product documentation

See [`docs/agents.md`](./docs/agents.md) for a concise, product-level overview of the intelligence roles behind each run.
