# BidForge UI system — layout wireframe (1280px max)

Reference grid: **8px base**, horizontal padding **20 / 32px**, max content width **1280px** (`BfContainer`).

## App shell (signed-in)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ SIDEBAR 240px          │ TOPBAR 56px h                                          │
│ ┌────────────┐         │                              [Theme] [Create] [@]  │
│ │ logo  BF   │         ├──────────────────────────────────────────────────────│
│ │            │         │ MAIN (px-8 py-10)                                      │
│ │ Overview   │         │  ┌──────────────────────────────────────────────────┐ │
│ │ New prop   │         │  │ page title (H1) + one line caption               │ │
│ │ Proposals  │         │  └──────────────────────────────────────────────────┘ │
│ │ Settings   │         │  … cards / split layout …                              │
│ └────────────┘         │                                                        │
└────────────────────────┴────────────────────────────────────────────────────────┘
```

Mobile: sidebar hidden; **horizontal chip nav** under topbar; same main padding `px-4`.

## Dashboard (`/dashboard`)

```
MAIN max 1280px
┌─────────────────────────────────────────────────────────┐
│ H1 "Overview" + caption (max-w-lg)                     │
└─────────────────────────────────────────────────────────┘
   40px gap (mt-10 md:mt-12)
┌─────────────────────────────────────────────────────────┐
│ PRIMARY CARD (BfCard, relative, gradient wash)         │
│  H2 "Start new proposal"                                │
│  body 1–2 lines                                         │
│  [ Create proposal ]  ← high contrast, 44px height     │
└─────────────────────────────────────────────────────────┘
   56px gap (mt-14)
H2 "Recent work" + caption
   24px gap
┌────────────┐ ┌────────────┐ ┌────────────┐
│ card       │ │ card       │ │ card       │   ← sm:2 col, lg:3 col, gap-4
│ title 2ln  │ │            │ │            │
│ meta       │ │            │ │            │
│ badges row │ │            │ │            │
└────────────┘ └────────────┘ └────────────┘
```

## Proposal workspace (`/proposal`)

```
MAIN max 1280px
Title block (mb-8 md:mb-10)

┌──────────────────────────── SplitPaneLayout ────────────────────────────┐
│ LEFT (input)                    │ RIGHT (output)                          │
│ p-6 md:p-8                      │ tabs row (Proposal | Issues | Score)    │
│ eyebrow INPUT                   ├─────────────────────────────────────────│
│ H2 "RFP or job description"     │ scroll area p-5 md:p-7                  │
│ helper 1 line                   │                                         │
│ ┌─────────────────────────────┐ │  Proposal: bordered inner “page”        │
│ │ textarea 14 rows            │ │  Issues: stacked rounded rows           │
│ └─────────────────────────────┘ │  Score: ScorePanel (score + 3 lists)    │
│ [Upload] [Generate proposal]   │                                         │
└─────────────────────────────────┴─────────────────────────────────────────┘
```

**Split ratio:** `lg:grid-cols-2` equal columns; stacked `< lg` with 24px gap.

## Landing (marketing)

1. **Sticky header** — logo left, theme + auth right (`BfContainer` width).
2. **Hero** — max text width **720px**, centered; CTA row gap **12 / 16px**.
3. **Product preview** — max **960px**, split mock (chrome + two columns).
4. **Problem / solution** — max text **640px**, generous vertical **py-20 md:py-28**.
5. **How it works** — `FlowSteps`: row on `md+` with arrow connectors; stacked on mobile.
6. **Example** — anchor `#example`, repeat preview or static block.
7. **Trust** — max **560px** centered, minimal list + one infrastructure line.
8. **Closing CTA** — card inset max **640px**.

## Typography tokens (use consistently)

| Role    | Classes / intent                                      |
| ------- | ----------------------------------------------------- |
| H1 hero | `font-display text-[1.85rem] sm:text-4xl md:text-[2.75rem] font-semibold tracking-[-0.035em]` |
| H2 sect | `font-display text-2xl md:text-3xl font-semibold tracking-[-0.03em]` |
| Body    | `text-[15px] md:text-base leading-relaxed`            |
| Caption | `text-[11px] uppercase tracking-[0.16em] text-muted-foreground` |
| Meta    | `text-[12px] text-muted-foreground`                   |

## Theme tokens (CSS variables)

- **Light:** `--background #fff`, `--card #f5f7fa`, `--border #e2e8f0`, foreground slate-900 family.
- **Dark:** `--background #0B0F19`, `--card #111624`, borders `white/9%`, foreground zinc-50 family.

Toggle: `next-themes` + `ThemeToggle` (header + settings). Default **dark** for first visit.

## Motion (Framer Motion)

- `MotionReveal`: `whileInView` fade + 14px rise, **once**, respects `prefers-reduced-motion`.
- `LandingProductPreview` / `FlowSteps`: same; no infinite loops on content.

## Components (`components/bidforge/`)

| Component        | Role                                      |
| ---------------- | ----------------------------------------- |
| `BfContainer`    | Max 1280px + horizontal padding           |
| `BfCard`         | Primary surface; `interactive` for links |
| `SectionHeader`  | Eyebrow + title + optional description    |
| `BfBadge`        | status / score / risk / neutral           |
| `CtaButton`      | Primary/secondary CTAs (optional use)     |
| `SplitPaneLayout`| Proposal workspace columns                |
| `ScorePanel`     | Score + missing coverage / weak / risks |
| `FlowSteps`      | Connected step cards + arrows             |
| `MotionReveal`   | Section enter animation                   |
| `ThemeToggle`    | Sun/moon control                          |
