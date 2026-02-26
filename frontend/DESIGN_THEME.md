# Beazley Design & Theme Guide

Design and theme reference for the Intelligent Ingestion app under Beazley’s domain. Use this when styling UI, adding components, or updating the theme.

---

## Color palette

Official Beazley palette (hex). Use these as the single source of truth for brand colors. Usage below follows the Beazley website: deep purple backgrounds, bright pink accent for links and highlights, white text on dark.

| Name | Hex | Use (Beazley site) |
|------|-----|--------------------|
| **Beazley Pink** | `#D91AA6` | **Primary accent:** full-width alert/news banners, highlighted words in headlines, links (“Find out more”), link underlines, focus rings |
| **Beazley Purple** | `#4F0259` | **Primary background:** main page background, top header bar, main navigation bar (dominant brand surface) |
| **Beazley Dark** | `#380140` | **Deep contrast:** darkest surfaces, footers, areas needing strongest contrast with white text |
| **Beazley Plum** | `#B31186` | **Secondary accent:** hover on links/buttons, secondary CTAs, charts, supporting emphasis |
| **Beazley Light** | `#F2F2F2` | **Light neutrals:** light-mode section backgrounds, cards, borders; search/input backgrounds (e.g. large rounded search bar) |
| **White** | `#FFFFFF` | **Text on dark:** logo, navigation links, body and headline text on purple/dark backgrounds; input fields |
| **Light grey** | `#CCCCCC` | **Subtle text:** placeholders (e.g. “Search our site”), secondary copy on dark |

### Quick reference (copy-paste)

```
#D91AA6  Beazley Pink   (accent: banners, links, highlights)
#4F0259  Beazley Purple (main background: header, nav, page)
#380140  Beazley Dark   (deep surfaces)
#B31186  Beazley Plum   (secondary accent, hover)
#F2F2F2  Beazley Light  (light backgrounds, inputs)
#FFFFFF  White          (text on dark)
#CCCCCC  Light grey     (placeholders)
```

---

## Usage guidelines

- **Page & nav background**: Beazley Purple (`#4F0259`) as the dominant background (header, main nav, main page area). Use Beazley Dark (`#380140`) for deeper sections or footers.
- **Text on dark**: White (`#FFFFFF`) for logo, navigation, headlines, and body copy on purple/dark. Use light grey (`#CCCCCC`) only for placeholders or low-emphasis text.
- **Accent (Beazley Pink `#D91AA6`)**: Full-width alert/news banners; key words or phrases in headlines; all interactive links; “Find out more”–style CTAs. Pair with underline on links.
- **Secondary accent (Beazley Plum `#B31186`)**: Hover states on links/buttons, secondary actions, charts.
- **Light mode / inputs**: Beazley Light (`#F2F2F2`) or white for section backgrounds and for large, rounded input fields (e.g. search).
- **Contrast**: Keep white text on Beazley Purple/Dark/Pink for readability. Ensure any text on accent backgrounds meets accessibility contrast.

---

## Implementation

Theme variables are defined in **`client/src/index.css`**:

- **Light** (`:root`): primary and accent map to Beazley Purple and Pink (HSL equivalents).
- **Dark** (`.dark`): background and primary use dark purple tones; accent uses pink.

When adding new UI:

1. Prefer semantic tokens: `bg-primary`, `text-primary`, `bg-accent`, `ring-accent`, etc.
2. For one-off brand use (e.g. charts, inline styles), import from `client/src/theme/design-tokens.ts`: `BEAZLEY_PALETTE` or `BEAZLEY_PALETTE_ARRAY`.

---

## Typography

Aligned with the Beazley site: sans-serif for all UI and content; accent color for headline emphasis and links.

- **Sans (ABC Diatype)**: Primary for body, navigation, and UI. Weights: 400 (body, placeholders), 500–700 (nav, headings, emphasis).
- **Serif (Tiempos Headline)**: Optional for display/headlines (h1–h6). On the site, headlines use sans with accent color for key phrases.
- **Mono (JetBrains Mono)**: Code and data only.
- **Headlines**: Use white (on dark) or dark (on light); for emphasis, use Beazley Pink on key words or phrases, slightly bolder/larger.
- **Links**: Beazley Pink + underline. Regular or semi-bold weight.

Defined in `client/src/index.css` via `@font-face` and `@theme inline` (`--font-sans`, `--font-serif`, `--font-mono`).

---

## Layout & structure

Following the Beazley homepage pattern:

- **Header**: Two-tier — (1) narrow utility bar (small text, left: locale/contact, right: Log in, Claims, Search, etc.); (2) main nav bar with logo left (white wordmark), main nav items centered (white, with dropdown indicators).
- **Alert/news banner**: Optional full-width strip in Beazley Pink below main nav for “LATEST FROM BEAZLEY”–style alerts; white or dark text, with “Find out more →” link in accent.
- **Hero / main content**: Prominent central area; headline and supporting text left-aligned; key phrase or CTA in accent with link + underline.
- **Search / inputs**: Large, rounded, light background (white or Beazley Light); placeholder in light grey; magnifying glass or action icon inside the field (e.g. right-aligned).

---

## Interactive elements

- **Links**: Beazley Pink (`#D91AA6`), underlined. Use Beazley Plum for hover if a distinct hover state is needed.
- **Primary CTAs** (e.g. “Find out more”): Same as links — accent color + underline; no button required for inline CTAs.
- **Buttons** (when used): Primary = Beazley Pink or Beazley Purple; ensure label is white for contrast.
- **Icons** (nav, utility bar, banner): White on dark backgrounds; simple, minimal style.

---

## Radii & spacing

- **Radii**: `--radius-sm` 2px → `--radius-xl` 8px (Tailwind `rounded-*`).
- **Default radius**: `--radius: 0.5rem` for components.

Use Tailwind spacing scale for consistency.

---

## Summary

| Role | Use (from Beazley site) |
|------|-------------------------|
| **Page / header / nav background** | Beazley Purple (dominant), Beazley Dark (deep) |
| **Text on dark** | White (primary), Light grey (placeholders only) |
| **Accent (banners, links, highlights)** | Beazley Pink; underline on links |
| **Secondary accent (hover, charts)** | Beazley Plum |
| **Light surfaces & inputs** | Beazley Light, White |
| **Layout** | Utility bar → Main nav → Optional pink banner → Hero/content → Prominent rounded search/inputs |

Keep this file updated when the Beazley palette or site patterns change.
