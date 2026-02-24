import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Format an annotation value for display.
 * Handles both string values and array values (e.g., hierarchy_path).
 * 
 * @param value - The annotation value (string, array, or any)
 * @param maxLength - Maximum length before truncating (default: 50)
 * @returns Formatted string for display
 */
export function formatAnnotationValue(value: unknown, maxLength: number = 50): string {
  if (value === null || value === undefined) {
    return '';
  }
  
  let displayStr: string;
  
  if (Array.isArray(value)) {
    // For arrays (like hierarchy_path), join with " > " for display
    displayStr = value.map(v => String(v)).join(' > ');
  } else {
    displayStr = String(value);
  }
  
  if (maxLength > 0 && displayStr.length > maxLength) {
    return displayStr.substring(0, maxLength) + '...';
  }
  
  return displayStr;
}
