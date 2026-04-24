# BidForge web (`apps/web`)

Next.js app for drafting and reviewing proposals. The UI talks to the FastAPI service under `api/` via `@bidforge/web-sdk`.

## Setup

From the **repository root** (Turbo uses the root `package.json`):

```bash
cp apps/web/.env.example apps/web/.env.local
# Add Clerk keys from https://dashboard.clerk.com

npm install
npm run dev
```

Open the URL printed in the terminal (typically http://localhost:3000).

## Layout

- `app/` — routes and layouts  
- `components/proposal/` — proposal workspace, review, markdown helpers  
- `lib/api/` — SDK helpers (`publicRunToProposalSections`, etc.)

## API dependency

Generation and persistence require the Python API. See the root **[`README.md`](../README.md)** for `api/.env` and `uvicorn` startup.
