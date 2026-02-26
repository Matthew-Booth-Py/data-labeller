/**
 * TextSpanAnnotator - Component for annotating text with inline span selection
 * Styled to match the Beazley data labeller theme
 */

import { useEffect, useRef, useCallback } from "react";
import type { GroundTruthAnnotation, TextSpanData } from "@/lib/api";
import { BEAZLEY_PALETTE } from "@/theme/design-tokens";

export interface EntityType {
  id: string;
  name: string;
  color: string;
}

interface TextSpanAnnotatorProps {
  text: string;
  annotations: GroundTruthAnnotation[];
  entityTypes: EntityType[];
  activeEntityTypeId: string | null;
  onAnnotationCreate: (
    fieldName: string,
    value: string,
    data: TextSpanData,
  ) => void;
  onAnnotationDelete: (annotationId: string) => void;
  onActiveEntityChange: (id: string | null) => void;
}

export function TextSpanAnnotator({
  text,
  annotations,
  entityTypes,
  activeEntityTypeId,
  onAnnotationCreate,
  onAnnotationDelete,
  onActiveEntityChange,
}: TextSpanAnnotatorProps) {
  const displayRef = useRef<HTMLDivElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);

  // Get text offset from a DOM node position
  const getTextOffset = useCallback((node: Node, offset: number): number => {
    if (!displayRef.current) return -1;

    const walker = document.createTreeWalker(
      displayRef.current,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode: (n) => {
          // Skip text nodes inside label tags (UI chrome, not document text)
          if ((n.parentElement as HTMLElement)?.closest(".dl-label-tag")) {
            return NodeFilter.FILTER_REJECT;
          }
          return NodeFilter.FILTER_ACCEPT;
        },
      },
    );

    let charCount = 0;
    while (walker.nextNode()) {
      if (walker.currentNode === node) {
        return charCount + offset;
      }
      charCount += walker.currentNode.textContent?.length || 0;
    }
    return -1;
  }, []);

  // Handle text selection
  const handleMouseUp = useCallback(
    (e: MouseEvent) => {
      const popup = popupRef.current;
      if (!popup) return;

      // Check if click was on a label tag (to remove annotation)
      const target = e.target as HTMLElement;
      if (target.classList.contains("dl-label-tag")) {
        const span = target.parentElement;
        const annId = span?.dataset.annotationId;
        if (annId) {
          onAnnotationDelete(annId);
          popup.classList.remove("visible");
          return;
        }
      }

      const selection = window.getSelection();
      if (!selection || selection.isCollapsed || !selection.rangeCount) {
        popup.classList.remove("visible");
        return;
      }

      const range = selection.getRangeAt(0);

      // Check if selection is within the text display
      if (
        !displayRef.current?.contains(range.startContainer) ||
        !displayRef.current?.contains(range.endContainer)
      ) {
        return;
      }

      if (!text) return;

      const startOffset = getTextOffset(
        range.startContainer,
        range.startOffset,
      );
      const endOffset = getTextOffset(range.endContainer, range.endOffset);

      if (startOffset < 0 || endOffset < 0 || startOffset === endOffset) {
        popup.classList.remove("visible");
        return;
      }

      const selStart = Math.min(startOffset, endOffset);
      const selEnd = Math.max(startOffset, endOffset);
      const selectedText = text.substring(selStart, selEnd);

      // If there's an active entity type, apply it directly
      if (activeEntityTypeId) {
        const entityType = entityTypes.find(
          (et) => et.id === activeEntityTypeId,
        );
        if (entityType) {
          onAnnotationCreate(entityType.name, selectedText, {
            start: selStart,
            end: selEnd,
            text: selectedText,
          });
        }
        selection.removeAllRanges();
        popup.classList.remove("visible");
        return;
      }

      // Otherwise show popup to pick entity type
      if (entityTypes.length === 0) return;

      // Group entity types by parent
      const grouped: Record<string, typeof entityTypes> = {};
      entityTypes.forEach((et) => {
        const parts = et.name.split(".");
        const parent = parts.length > 1 ? parts[0] : "_root";
        if (!grouped[parent]) grouped[parent] = [];
        grouped[parent].push(et);
      });

      // Build popup content with hierarchy
      let popupHtml = "";
      Object.entries(grouped).forEach(([parent, types]) => {
        popupHtml += `<div class="dl-popup-group">`;
        if (parent !== "_root") {
          popupHtml += `<div class="dl-popup-group-title">${escapeHtml(parent)}</div>`;
        }
        popupHtml += `<div class="dl-popup-group-buttons">`;
        types.forEach((et) => {
          const displayName = et.name.split(".").pop() || et.name;
          popupHtml += `<button class="dl-popup-entity-btn" style="background:${et.color}30; color:${et.color}; border-color:${et.color}66"
           data-entity-id="${et.id}" data-start="${selStart}" data-end="${selEnd}">${escapeHtml(displayName)}</button>`;
        });
        popupHtml += `</div></div>`;
      });

      popup.innerHTML = popupHtml;

      // Position popup near the selection
      const rect = range.getBoundingClientRect();
      popup.style.left = `${Math.min(rect.left, window.innerWidth - 300)}px`;
      popup.style.top = `${rect.bottom + 8}px`;
      popup.classList.add("visible");
    },
    [
      text,
      activeEntityTypeId,
      entityTypes,
      onAnnotationCreate,
      onAnnotationDelete,
      getTextOffset,
    ],
  );

  // Handle popup button clicks
  const handlePopupClick = useCallback(
    (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.classList.contains("dl-popup-entity-btn")) {
        const entityId = target.dataset.entityId;
        const start = parseInt(target.dataset.start || "0", 10);
        const end = parseInt(target.dataset.end || "0", 10);

        const entityType = entityTypes.find((et) => et.id === entityId);
        if (entityType && text) {
          const selectedText = text.substring(start, end);
          onAnnotationCreate(entityType.name, selectedText, {
            start,
            end,
            text: selectedText,
          });
        }

        window.getSelection()?.removeAllRanges();
        popupRef.current?.classList.remove("visible");
      }
    },
    [entityTypes, text, onAnnotationCreate],
  );

  // Close popup on outside click
  const handleMouseDown = useCallback((e: MouseEvent) => {
    const popup = popupRef.current;
    if (popup && !popup.contains(e.target as Node)) {
      popup.classList.remove("visible");
    }
  }, []);

  // Keyboard shortcuts
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA") return;

      // Number keys 1-9 to select entity type
      if (
        e.key >= "1" &&
        e.key <= "9" &&
        !e.ctrlKey &&
        !e.metaKey &&
        !e.altKey
      ) {
        const idx = parseInt(e.key) - 1;
        if (idx < entityTypes.length) {
          const entityType = entityTypes[idx];
          onActiveEntityChange(
            activeEntityTypeId === entityType.id ? null : entityType.id,
          );
          e.preventDefault();
        }
      }

      // Escape to deselect
      if (e.key === "Escape") {
        onActiveEntityChange(null);
        popupRef.current?.classList.remove("visible");
        window.getSelection()?.removeAllRanges();
      }

      // Delete/Backspace to remove last annotation
      if (e.key === "Delete" || e.key === "Backspace") {
        if (annotations.length > 0) {
          const lastAnnotation = annotations[annotations.length - 1];
          onAnnotationDelete(lastAnnotation.id);
          e.preventDefault();
        }
      }

      // Ctrl+Z to undo last annotation
      if ((e.ctrlKey || e.metaKey) && e.key === "z") {
        if (annotations.length > 0) {
          const lastAnnotation = annotations[annotations.length - 1];
          onAnnotationDelete(lastAnnotation.id);
          e.preventDefault();
        }
      }
    },
    [
      entityTypes,
      activeEntityTypeId,
      annotations,
      onActiveEntityChange,
      onAnnotationDelete,
    ],
  );

  // Set up event listeners
  useEffect(() => {
    document.addEventListener("mouseup", handleMouseUp);
    document.addEventListener("mousedown", handleMouseDown);
    document.addEventListener("keydown", handleKeyDown);
    popupRef.current?.addEventListener("click", handlePopupClick);

    return () => {
      document.removeEventListener("mouseup", handleMouseUp);
      document.removeEventListener("mousedown", handleMouseDown);
      document.removeEventListener("keydown", handleKeyDown);
      popupRef.current?.removeEventListener("click", handlePopupClick);
    };
  }, [handleMouseUp, handleMouseDown, handleKeyDown, handlePopupClick]);

  // Render text with annotation highlights
  const renderAnnotatedText = () => {
    if (!text) {
      return (
        <div className="dl-empty-state">
          <div className="dl-empty-state-icon">📄</div>
          <div className="dl-empty-state-text">No text loaded</div>
          <div className="dl-empty-state-hint">
            Select a document to start labelling
          </div>
        </div>
      );
    }

    // Filter to text_span annotations and sort by start position
    const textAnnotations = annotations
      .filter((a) => a.annotation_type === "text_span")
      .sort((a, b) => {
        const aData = a.annotation_data as TextSpanData;
        const bData = b.annotation_data as TextSpanData;
        return (aData?.start || 0) - (bData?.start || 0);
      });

    if (textAnnotations.length === 0) {
      return <>{text}</>;
    }

    const segments: React.ReactNode[] = [];
    let pos = 0;

    for (const ann of textAnnotations) {
      const data = ann.annotation_data as TextSpanData;
      if (!data || data.start === undefined) continue;

      if (data.start < pos) continue; // Skip overlapping

      // Add text before this annotation
      if (data.start > pos) {
        segments.push(
          <span key={`text-${pos}`}>{text.substring(pos, data.start)}</span>,
        );
      }

      // Find entity type for color
      const entityType = entityTypes.find((et) => et.name === ann.field_name);
      const color = entityType?.color || BEAZLEY_PALETTE.light;
      const bgColor = color + "30";

      // Build tooltip with row number if available
      const instanceNum = (ann.annotation_data as any)?.instance_num;
      const tooltipText = instanceNum
        ? `Row ${instanceNum} | ${ann.field_name}: ${ann.value}`
        : `${ann.field_name}: ${ann.value}`;

      // Add annotation span
      segments.push(
        <span
          key={`ann-${ann.id}`}
          className="dl-annotation-span"
          style={{
            background: bgColor,
            borderBottom: `2px solid ${color}`,
            color: color,
          }}
          data-annotation-id={ann.id}
          title={tooltipText}
        >
          {text.substring(data.start, data.end)}
          <span
            className="dl-label-tag"
            style={{ background: color, color: BEAZLEY_PALETTE.dark }}
          >
            {ann.field_name}
          </span>
        </span>,
      );

      pos = data.end;
    }

    // Add remaining text
    if (pos < text.length) {
      segments.push(<span key={`text-end`}>{text.substring(pos)}</span>);
    }

    return <>{segments}</>;
  };

  return (
    <>
      <div className="dl-text-display-container">
        <div ref={displayRef} className="dl-text-display">
          {renderAnnotatedText()}
        </div>
      </div>

      {/* Label popup */}
      <div ref={popupRef} className="dl-annotation-popup" />
    </>
  );
}

// Expose scroll function for external use
TextSpanAnnotator.scrollToAnnotation = (id: string) => {
  const span = document.querySelector(
    `[data-annotation-id="${id}"]`,
  ) as HTMLElement;
  if (span) {
    span.scrollIntoView({ behavior: "smooth", block: "center" });
    span.classList.add("dl-focus-outline");
    setTimeout(() => {
      span.classList.remove("dl-focus-outline");
    }, 1200);
  }
};

function escapeHtml(str: string): string {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
