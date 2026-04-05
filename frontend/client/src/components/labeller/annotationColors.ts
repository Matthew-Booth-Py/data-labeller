const DARK_TEXT = "#2D0833";
const LIGHT_TEXT = "#FFFFFF";

interface RgbColor {
  r: number;
  g: number;
  b: number;
}

function expandShortHex(hex: string): string {
  return hex
    .slice(1)
    .split("")
    .map((char) => char + char)
    .join("");
}

function parseColor(color: string): RgbColor | null {
  const normalized = color.trim();

  if (normalized.startsWith("#")) {
    const rawHex =
      normalized.length === 4 ? expandShortHex(normalized) : normalized.slice(1);
    if (rawHex.length !== 6 || /[^0-9a-f]/i.test(rawHex)) {
      return null;
    }

    return {
      r: Number.parseInt(rawHex.slice(0, 2), 16),
      g: Number.parseInt(rawHex.slice(2, 4), 16),
      b: Number.parseInt(rawHex.slice(4, 6), 16),
    };
  }

  const rgbMatch = normalized.match(
    /^rgba?\(\s*(\d{1,3})[\s,]+(\d{1,3})[\s,]+(\d{1,3})(?:[\s,\/]+[\d.]+)?\s*\)$/i,
  );
  if (!rgbMatch) {
    return null;
  }

  return {
    r: Number.parseInt(rgbMatch[1] || "0", 10),
    g: Number.parseInt(rgbMatch[2] || "0", 10),
    b: Number.parseInt(rgbMatch[3] || "0", 10),
  };
}

function toLinearChannel(value: number): number {
  const normalized = value / 255;
  return normalized <= 0.03928
    ? normalized / 12.92
    : ((normalized + 0.055) / 1.055) ** 2.4;
}

function relativeLuminance(color: RgbColor): number {
  return (
    0.2126 * toLinearChannel(color.r) +
    0.7152 * toLinearChannel(color.g) +
    0.0722 * toLinearChannel(color.b)
  );
}

function contrastRatio(a: string, b: string): number {
  const parsedA = parseColor(a);
  const parsedB = parseColor(b);
  if (!parsedA || !parsedB) {
    return 0;
  }

  const luminanceA = relativeLuminance(parsedA);
  const luminanceB = relativeLuminance(parsedB);
  const lighter = Math.max(luminanceA, luminanceB);
  const darker = Math.min(luminanceA, luminanceB);
  return (lighter + 0.05) / (darker + 0.05);
}

export function alphaColor(color: string, alpha: number): string {
  const parsed = parseColor(color);
  if (!parsed) {
    return color;
  }

  const clampedAlpha = Math.max(0, Math.min(1, alpha));
  return `rgba(${parsed.r}, ${parsed.g}, ${parsed.b}, ${clampedAlpha})`;
}

export function getReadableTextColor(backgroundColor: string): string {
  const darkContrast = contrastRatio(backgroundColor, DARK_TEXT);
  const lightContrast = contrastRatio(backgroundColor, LIGHT_TEXT);
  return lightContrast > darkContrast ? LIGHT_TEXT : DARK_TEXT;
}
