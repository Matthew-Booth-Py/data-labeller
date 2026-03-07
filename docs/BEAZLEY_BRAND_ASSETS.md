# Beazley Brand Assets

> **Stack:** React 19 · Tailwind CSS v4

---

## Logo

<img src="brand_assets/logo.svg" alt="Beazley b-mark" width="72" height="72" />

The Beazley "b" mark. Always used at 36 × 36 px in the sidebar; can scale up for splash screens.

| Property | Value |
|---|---|
| Circle fill | `#DC199B` |
| Letterform | `#FFFFFF` |
| Sidebar size | `h-9 w-9` (36 px) |

```tsx
<img src="/logo.svg" alt="Beazley Logo" className="h-9 w-9" />
```

---

## Color Palette

### Brand Primitives

| Swatch | Token | Hex | Usage |
|---|---|---|---|
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#D91AA6;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `pink` | `#D91AA6` | Primary accent — CTAs, links, focus rings, highlights |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#4F0259;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `purple` | `#4F0259` | Dominant brand surface — sidebar, header, primary buttons |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#380140;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `dark` | `#380140` | Deep contrast — footers, button hover, deepest shadows |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#B31186;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `plum` | `#B31186` | Secondary accent — hover states, chart series 2 |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#F2F2F2;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `light` | `#F2F2F2` | Light neutral — card/section backgrounds, inputs |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#FFFFFF;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `white` | `#FFFFFF` | Text and icons on dark surfaces |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#CCCCCC;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `grey` | `#CCCCCC` | Placeholder / low-emphasis text on dark |

### Semantic Tokens (light mode)

Applied as CSS custom properties on `:root`. Use these in components, never raw hex.

| Swatch | CSS var | Hex | Role |
|---|---|---|---|
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#F8F4F8;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `--surface-page` | `#F8F4F8` | Page/app background |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#FFFFFF;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `--surface-panel` | `#FFFFFF` | Cards, panels, inputs |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#FBF9FB;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `--surface-elevated` | `#FBF9FB` | Dropdowns, page headers, modals |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#2D0833;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `--text-primary` | `#2D0833` | Body text, headings |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#5F4464;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `--text-secondary` | `#5F4464` | Labels, descriptions |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#7D6882;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `--text-tertiary` | `#7D6882` | Muted / placeholder text |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#4F0259;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `--interactive-primary` | `#4F0259` | Primary buttons, sidebar active |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#380140;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `--interactive-primary-hover` | `#380140` | Primary button hover |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#D91AA6;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `--interactive-accent` | `#D91AA6` | Accent CTAs, active indicators, focus ring |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#B31186;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `--interactive-accent-hover` | `#B31186` | Accent hover |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#E9E1EB;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `--border-subtle` | `#E9E1EB` | Default card/input borders |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#D7CDD9;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `--border-strong` | `#D7CDD9` | Hover/active borders |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#0E9F6E;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `--status-success` | `#0E9F6E` | Success |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#C27803;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `--status-warn` | `#C27803` | Warning |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#D1344B;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | `--status-error` | `#D1344B` | Error / destructive |

### Dark Mode

When `.dark` is applied, pink takes over as the primary interactive color.

| Swatch | Role | Dark value |
|---|---|---|
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#140F18;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | Page background | `#140F18` |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#1A1420;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | Panel / card | `#1A1420` |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#201828;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | Elevated surface | `#201828` |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#D91AA6;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | Interactive primary | `#D91AA6` |
| <span style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#F5EFF7;vertical-align:middle;border:1px solid rgba(0,0,0,.12);"></span> | Text primary | `#F5EFF7` |

---

## Typography

### Font Stack

| Role | Family | Fallback | Tailwind class |
|---|---|---|---|
| Sans (body, UI) | ABC Diatype | IBM Plex Sans, sans-serif | `font-sans` |
| Serif (headings) | Tiempos Headline | serif | `font-serif` |
| Mono (code, output) | JetBrains Mono | SF Mono, monospace | `font-mono` |

> **Note:** ABC Diatype and Tiempos Headline are commercial fonts and are not included in the repo.
> - **ABC Diatype** — available from [Dinamo](https://abcdinamo.com/typefaces/diatype) (Regular, Medium, Bold)
> - **Tiempos Headline** — available from [Klim Type Foundry](https://klim.co.nz/retail-fonts/tiempos-headline/) (Medium)
