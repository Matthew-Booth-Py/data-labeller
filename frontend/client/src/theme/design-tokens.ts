/**
 * Beazley design tokens — single source for palette hex values.
 * See frontend/DESIGN_THEME.md for usage and guidelines (aligned with Beazley site).
 */
export const BEAZLEY_PALETTE = {
  /** Primary accent: banners, links, headline highlights, link underlines (#D91AA6) */
  pink: "#D91AA6",
  /** Main background: header, nav, page (dominant brand surface) (#4F0259) */
  purple: "#4F0259",
  /** Deep surfaces: footers, strongest contrast (#380140) */
  dark: "#380140",
  /** Secondary accent: hover, secondary CTAs, charts (#B31186) */
  plum: "#B31186",
  /** Light surfaces: section backgrounds, cards, input backgrounds (#F2F2F2) */
  light: "#F2F2F2",
  /** Text on dark: logo, nav, body, headlines (#FFFFFF) */
  white: "#FFFFFF",
  /** Placeholders and subtle text on dark (#CCCCCC) */
  grey: "#CCCCCC",
} as const;

export type BeazleyPaletteKey = keyof typeof BEAZLEY_PALETTE;

/** Array of palette hex values for charts and gradients (pink, purple, dark, plum, light). */
export const BEAZLEY_PALETTE_ARRAY = Object.values(BEAZLEY_PALETTE);
