# UI Revamp Spec (Implemented Baseline)

## Goals

- Apply a cohesive Beazley brand-light product experience across all app surfaces.
- Use hybrid navigation: utility header + branded header + persistent project rail.
- Keep Data Labeller as a specialist dark surface, visually aligned but independent.

## Token Map

### Core HSL roles (`client/src/index.css`)

- `--background`, `--foreground`
- `--card`, `--card-foreground`
- `--primary`, `--primary-foreground`
- `--accent`, `--accent-foreground`
- `--secondary`, `--secondary-foreground`
- `--muted`, `--muted-foreground`
- `--border`, `--input`, `--ring`

### Semantic roles (direct CSS variables)

- `--surface-page`
- `--surface-panel`
- `--surface-elevated`
- `--text-primary`
- `--text-secondary`
- `--interactive-primary`
- `--interactive-primary-hover`
- `--interactive-accent`
- `--interactive-accent-hover`
- `--focus-ring`
- `--border-strong`
- `--border-subtle`
- `--status-success`
- `--status-warn`
- `--status-error`
- `--button-outline`
- `--badge-outline`

### Source palette (`client/src/theme/design-tokens.ts`)

- `BEAZLEY_PALETTE` remains the raw brand source.
- `BEAZLEY_SEMANTIC_TOKENS` defines semantic intent for app-wide usage.

## Motion + Elevation

- `hover-elevate`: restrained lift + shadow for interactive cards/actions.
- `active-elevate-2`: pressed state with inset depth.
- `focus-brand`: explicit brand focus ring utility.

## Component Usage Rules

### Buttons (`components/ui/button.tsx`)

- Primary actions: `variant="primary"` (default).
- Support actions: `variant="secondary"` or `variant="outline"`.
- Low-emphasis actions: `variant="quiet"` or `variant="ghost"`.
- Inline CTAs: `variant="link-accent"`.
- Risky actions: `variant="danger"` (alias `destructive` supported).

### Badges (`components/ui/badge.tsx`)

- Status and role tags: `primary`, `secondary`, `accent`, `quiet`, `danger`, `outline`.

### Inputs / Tabs / Cards

- Inputs use panel surfaces and stronger focus rings.
- Tabs use bordered elevated list containers with active-state emphasis.
- Cards use subtle borders and restrained lift for readability.

## Typography Scale

- Display/page title: `text-3xl` / `text-2xl`
- Section headers: `text-lg` / `text-base`
- Body: `text-sm` / `text-base`
- Meta/helper/captions: `text-xs`
- Mono contexts: IDs, model names, endpoint snippets, schema keys

## Spacing Scale

- Page shell content gutters: `px-4 md:px-8`
- Primary vertical rhythm: `space-y-6` / `space-y-8`
- Card interior spacing: `p-4` to `p-6`
- Dense row controls: `h-8` to `h-10`

## Screen Intent (Before -> After)

### Shell / App Chrome

- Before: simple sidebar + top strip.
- After: two-tier top header + responsive project rail + mobile drawer navigation.

### Dashboard

- Before: basic metric cards.
- After: executive hero, KPI strips, activity posture, quick action stack, active project launch grid.

### Projects

- Before: card list with local controls.
- After: structured shell header actions + clearer project card hierarchy retained.

### Create Project

- Before: standalone form card.
- After: guided setup framed under global shell and clearer action hierarchy.

### Fields Library

- Before: list-heavy page with local header.
- After: shell-driven heading/actions + denser field management surface with consistent controls.

### Settings

- Before: minimal split layout.
- After: explicit configured/unconfigured states with structured sections and status badges.

### Project Workspace

- Before: local project header + tabs.
- After: shell-owned project context, typed tab ids, clearer tab rail, and persistent workspace framing.

### Document Pool

- Before: wide ungrouped toolbar controls.
- After: grouped command panel, responsive control wrapping, improved view/action clarity.

### Schema Viewer

- Before: mixed spacing and panel hierarchy.
- After: panelized split surfaces with stronger section boundaries.

### Extraction Runner

- Before: linear form + output stack.
- After: two-column run panel and output narrative with status framing.

### Labels / Evaluate / Deployment / API

- Before: functional but uneven panel behavior.
- After: harmonized card/surface styles, responsive filter bars, clearer summary and action framing.

### Data Labeller

- Before: custom dark surface with system font.
- After: retains dark specialist model, aligned to shared typography and spacing language.

## Accessibility and Responsiveness Baseline

- Navigation collapses to drawer below `lg`.
- Headers remain sticky.
- Focus states are explicit on interactive controls.
- Table/filter surfaces are responsive with stacked controls on narrow widths.

## Verification Checklist

- `npm --prefix frontend run check` passes.
- Frontend build completes with token and class resolution intact.
- Validate key routes at desktop/tablet/mobile.
- Validate workflow continuity: project -> documents -> schema -> labels -> evaluate -> deployment.
