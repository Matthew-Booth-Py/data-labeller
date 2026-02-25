/**
 * PdfTextAnnotator - Component for annotating PDFs with text selection
 * Renders the actual PDF and allows highlighting text to create annotations
 */

import { useState, useRef, useCallback, useEffect } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { ZoomIn, ZoomOut, Loader2 } from "lucide-react";
import type {
  GroundTruthAnnotation,
  BoundingBoxData,
  AnnotationSuggestion,
} from "@/lib/api";
import type { EntityType } from "./TextSpanAnnotator";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.mjs`;

interface PdfTextAnnotatorProps {
  documentId: string;
  pdfUrl: string;
  annotations: GroundTruthAnnotation[];
  entityTypes: EntityType[];
  activeEntityTypeId: string | null;
  onAnnotationCreate: (
    fieldName: string,
    value: string,
    data: BoundingBoxData,
  ) => void;
  onAnnotationDelete: (annotationId: string) => void;
  onActiveEntityChange: (id: string | null) => void;
  suggestions?: AnnotationSuggestion[];
  onSuggestionApprove?: (suggestion: AnnotationSuggestion) => void;
  onSuggestionReject?: (id: string) => void;
}

interface AnnotationRect {
  leftPct: number;
  topPct: number;
  widthPct: number;
  heightPct: number;
}

interface PendingSelection {
  pageNum: number;
  text: string;
  rects: AnnotationRect[];
}

export function PdfTextAnnotator({
  documentId,
  pdfUrl,
  annotations,
  entityTypes,
  activeEntityTypeId,
  onAnnotationCreate,
  onAnnotationDelete,
  onActiveEntityChange,
  suggestions = [],
  onSuggestionApprove,
  onSuggestionReject,
}: PdfTextAnnotatorProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [scale, setScale] = useState(1.5);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingSelection, setPendingSelection] =
    useState<PendingSelection | null>(null);
  const [popupPosition, setPopupPosition] = useState<{
    x: number;
    y: number;
  } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);

  // Get active entity type
  const activeEntityType = entityTypes.find(
    (et) => et.id === activeEntityTypeId,
  );

  // Handle PDF load success
  const onDocumentLoadSuccess = useCallback(
    ({ numPages }: { numPages: number }) => {
      setNumPages(numPages);
      setIsLoading(false);
      setError(null);
    },
    [],
  );

  // Handle PDF load error
  const onDocumentLoadError = useCallback((err: Error) => {
    console.error("PDF load error:", err);
    setError(err.message || "Failed to load PDF");
    setIsLoading(false);
  }, []);

  // Get color for an entity type
  const getEntityColor = useCallback(
    (fieldName: string): string => {
      const et = entityTypes.find((e) => e.name === fieldName);
      return et?.color || "#8b949e";
    },
    [entityTypes],
  );

  // Handle text selection
  const handleMouseUp = useCallback(
    (e: MouseEvent) => {
      const selection = window.getSelection();
      if (!selection || selection.isCollapsed || !selection.rangeCount) {
        setPopupPosition(null);
        setPendingSelection(null);
        return;
      }

      const range = selection.getRangeAt(0);

      // Find the page containing the selection
      const startPage = (
        range.startContainer.parentElement as HTMLElement
      )?.closest(".react-pdf__Page");
      const endPage = (
        range.endContainer.parentElement as HTMLElement
      )?.closest(".react-pdf__Page");

      if (!startPage || !endPage || startPage !== endPage) {
        setPopupPosition(null);
        setPendingSelection(null);
        return;
      }

      // Check if selection is in text layer
      const textLayer = (
        range.startContainer.parentElement as HTMLElement
      )?.closest(".react-pdf__Page__textContent");
      if (!textLayer) {
        setPopupPosition(null);
        setPendingSelection(null);
        return;
      }

      const pageNum = parseInt(
        startPage.getAttribute("data-page-number") || "1",
      );
      const selectedText = selection.toString();

      if (!selectedText.trim()) {
        setPopupPosition(null);
        setPendingSelection(null);
        return;
      }

      // Get rects relative to page as percentages
      const pageRect = startPage.getBoundingClientRect();
      const clientRects = range.getClientRects();
      const rects: AnnotationRect[] = [];

      for (let i = 0; i < clientRects.length; i++) {
        const r = clientRects[i];
        if (r.width < 1 || r.height < 1) continue;
        rects.push({
          leftPct: ((r.left - pageRect.left) / pageRect.width) * 100,
          topPct: ((r.top - pageRect.top) / pageRect.height) * 100,
          widthPct: (r.width / pageRect.width) * 100,
          heightPct: (r.height / pageRect.height) * 100,
        });
      }

      if (rects.length === 0) {
        setPopupPosition(null);
        setPendingSelection(null);
        return;
      }

      // If active entity type, apply directly
      if (activeEntityTypeId && activeEntityType) {
        const bbox: BoundingBoxData = {
          page: pageNum,
          x: rects[0].leftPct,
          y: rects[0].topPct,
          width:
            rects.reduce((max, r) => Math.max(max, r.leftPct + r.widthPct), 0) -
            rects[0].leftPct,
          height:
            rects.reduce((max, r) => Math.max(max, r.topPct + r.heightPct), 0) -
            rects[0].topPct,
          text: selectedText.trim(),
        };
        onAnnotationCreate(activeEntityType.name, selectedText.trim(), bbox);
        selection.removeAllRanges();
        setPopupPosition(null);
        setPendingSelection(null);
        return;
      }

      // Show popup to pick entity type
      if (entityTypes.length === 0) return;

      setPendingSelection({ pageNum, text: selectedText, rects });
      const rect = range.getBoundingClientRect();
      setPopupPosition({
        x: Math.min(rect.left, window.innerWidth - 300),
        y: rect.bottom + 8,
      });
    },
    [activeEntityTypeId, activeEntityType, entityTypes, onAnnotationCreate],
  );

  // Apply annotation from popup
  const applyFromPopup = useCallback(
    (entityTypeId: string) => {
      if (!pendingSelection) return;

      const entityType = entityTypes.find((et) => et.id === entityTypeId);
      if (!entityType) return;

      const { pageNum, text, rects } = pendingSelection;
      const bbox: BoundingBoxData = {
        page: pageNum,
        x: rects[0].leftPct,
        y: rects[0].topPct,
        width:
          rects.reduce((max, r) => Math.max(max, r.leftPct + r.widthPct), 0) -
          rects[0].leftPct,
        height:
          rects.reduce((max, r) => Math.max(max, r.topPct + r.heightPct), 0) -
          rects[0].topPct,
        text: text.trim(),
      };

      onAnnotationCreate(entityType.name, text.trim(), bbox);
      window.getSelection()?.removeAllRanges();
      setPopupPosition(null);
      setPendingSelection(null);
    },
    [pendingSelection, entityTypes, onAnnotationCreate],
  );

  // Close popup on outside click
  const handleMouseDown = useCallback((e: MouseEvent) => {
    if (popupRef.current && !popupRef.current.contains(e.target as Node)) {
      setPopupPosition(null);
      setPendingSelection(null);
    }
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
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
        setPopupPosition(null);
        setPendingSelection(null);
        window.getSelection()?.removeAllRanges();
      }

      // Delete/Backspace to remove last annotation
      if (e.key === "Delete" || e.key === "Backspace") {
        const pdfAnnotations = annotations.filter(
          (a) => a.annotation_type === "bbox",
        );
        if (pdfAnnotations.length > 0) {
          const lastAnnotation = pdfAnnotations[pdfAnnotations.length - 1];
          onAnnotationDelete(lastAnnotation.id);
          e.preventDefault();
        }
      }

      // Zoom shortcuts
      if ((e.key === "=" || e.key === "+") && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        setScale((s) => Math.min(4.0, s + 0.25));
      }
      if (e.key === "-" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        setScale((s) => Math.max(0.5, s - 0.25));
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("mouseup", handleMouseUp);
    document.addEventListener("mousedown", handleMouseDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mouseup", handleMouseUp);
      document.removeEventListener("mousedown", handleMouseDown);
    };
  }, [
    entityTypes,
    activeEntityTypeId,
    annotations,
    onActiveEntityChange,
    onAnnotationDelete,
    handleMouseUp,
    handleMouseDown,
  ]);

  // Render annotation highlights on a page
  const renderAnnotationHighlights = (pageNum: number) => {
    const pageAnnotations = annotations.filter(
      (a) =>
        a.annotation_type === "bbox" &&
        (a.annotation_data as BoundingBoxData).page === pageNum,
    );

    return pageAnnotations.map((ann) => {
      const bbox = ann.annotation_data as BoundingBoxData;
      const color = getEntityColor(ann.field_name);

      // Build tooltip with row number if available
      const instanceNum = bbox.instance_num;
      const tooltipText = instanceNum
        ? `Row ${instanceNum} | ${ann.field_name}: "${bbox.text || ann.value}"\nClick to delete`
        : `${ann.field_name}: "${bbox.text || ann.value}"\nClick to delete`;

      return (
        <div
          key={ann.id}
          data-annotation-id={ann.id}
          className="absolute pointer-events-auto cursor-pointer transition-all hover:brightness-125"
          style={{
            left: `${bbox.x}%`,
            top: `${bbox.y}%`,
            width: `${bbox.width}%`,
            height: `${bbox.height}%`,
            backgroundColor: `${color}40`,
            borderBottom: `2px solid ${color}`,
            borderRadius: "2px",
          }}
          onClick={() => onAnnotationDelete(ann.id)}
          title={tooltipText}
        />
      );
    });
  };

  // Render suggestion overlays on a page
  const renderSuggestionOverlays = (pageNum: number) => {
    const pageSuggestions = suggestions.filter(
      (s) =>
        s.annotation_type === "bbox" &&
        (s.annotation_data as BoundingBoxData).page === pageNum,
    );

    return pageSuggestions.map((suggestion) => {
      const bbox = suggestion.annotation_data as BoundingBoxData;
      const label =
        suggestion.field_name.split(".").pop() || suggestion.field_name;

      return (
        <div
          key={suggestion.id}
          className="absolute pointer-events-auto group"
          style={{
            left: `${bbox.x}%`,
            top: `${bbox.y}%`,
            width: `${bbox.width}%`,
            height: `${bbox.height}%`,
            backgroundColor: "rgba(240, 136, 62, 0.15)",
            border: "2px dashed #f0883e",
            borderRadius: "2px",
          }}
          title={`AI suggestion: ${suggestion.field_name}\n"${suggestion.value}"`}
        >
          {/* Label tag */}
          <div
            style={{
              position: "absolute",
              top: "-18px",
              left: 0,
              background: "#f0883e",
              color: "#0d1117",
              fontSize: "9px",
              fontWeight: 700,
              padding: "1px 4px",
              borderRadius: "3px",
              whiteSpace: "nowrap",
              display: "flex",
              alignItems: "center",
              gap: "4px",
            }}
          >
            ✦ {label}
            <button
              onClick={() => onSuggestionApprove?.(suggestion)}
              style={{
                background: "#238636",
                border: "none",
                color: "#fff",
                borderRadius: "2px",
                padding: "0 3px",
                cursor: "pointer",
                fontSize: "9px",
              }}
              title="Approve"
            >
              ✓
            </button>
            <button
              onClick={() => onSuggestionReject?.(suggestion.id)}
              style={{
                background: "#f85149",
                border: "none",
                color: "#fff",
                borderRadius: "2px",
                padding: "0 3px",
                cursor: "pointer",
                fontSize: "9px",
              }}
              title="Reject"
            >
              ✕
            </button>
          </div>
        </div>
      );
    });
  };

  return (
    <div className="flex flex-col h-full" style={{ background: "#0d1117" }}>
      {/* Toolbar */}
      <div
        className="flex items-center justify-between px-5 py-2 border-b"
        style={{ borderColor: "#30363d", background: "#161b22" }}
      >
        <div
          className="flex items-center gap-2 text-sm"
          style={{ color: "#8b949e" }}
        >
          {activeEntityType ? (
            <>
              <span
                className="w-3 h-3 rounded-full"
                style={{ background: activeEntityType.color }}
              />
              <span>
                Labelling as{" "}
                <strong style={{ color: "#c9d1d9" }}>
                  {activeEntityType.name}
                </strong>{" "}
                — highlight text to annotate
              </span>
            </>
          ) : entityTypes.length === 0 ? (
            <span>Add entity types in the sidebar to begin labelling</span>
          ) : (
            <span>Select an entity type, then highlight text to label it</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            className="dl-btn dl-btn-sm"
            onClick={() => setScale((s) => Math.max(0.5, s - 0.25))}
          >
            <ZoomOut size={14} />
          </button>
          <span
            className="text-sm font-mono"
            style={{ color: "#8b949e", minWidth: "50px", textAlign: "center" }}
          >
            {Math.round(scale * 100)}%
          </span>
          <button
            className="dl-btn dl-btn-sm"
            onClick={() => setScale((s) => Math.min(4.0, s + 0.25))}
          >
            <ZoomIn size={14} />
          </button>
        </div>
      </div>

      {/* PDF Viewer */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto"
        style={{ background: "#0d1117" }}
      >
        <Document
          file={pdfUrl}
          onLoadSuccess={onDocumentLoadSuccess}
          onLoadError={onDocumentLoadError}
          loading={
            <div
              className="flex flex-col items-center justify-center h-96 gap-3"
              style={{ color: "#8b949e" }}
            >
              <Loader2
                className="h-8 w-8 animate-spin"
                style={{ color: "#58a6ff" }}
              />
              <span>Loading PDF...</span>
            </div>
          }
          error={
            <div className="flex flex-col items-center justify-center h-96 gap-3">
              <span style={{ fontSize: "48px", opacity: 0.3 }}>⚠️</span>
              <span style={{ color: "#f85149" }}>Failed to load PDF</span>
              <span style={{ color: "#484f58", fontSize: "12px" }}>
                {error}
              </span>
            </div>
          }
        >
          <div className="flex flex-col items-center gap-4 p-6">
            {Array.from(new Array(numPages), (_, index) => (
              <div
                key={`page_${index + 1}`}
                className="relative"
                style={{
                  background: "#fff",
                  boxShadow: "0 2px 12px rgba(0,0,0,0.5)",
                }}
              >
                <Page
                  pageNumber={index + 1}
                  scale={scale}
                  renderTextLayer={true}
                  renderAnnotationLayer={false}
                />

                {/* Annotation overlay */}
                <div
                  className="absolute inset-0 pointer-events-none overflow-hidden"
                  style={{ zIndex: 10 }}
                >
                  {renderAnnotationHighlights(index + 1)}
                </div>

                {/* Suggestion overlay */}
                <div
                  className="absolute inset-0 overflow-visible"
                  style={{ zIndex: 11, pointerEvents: "none" }}
                >
                  <div
                    style={{
                      position: "relative",
                      width: "100%",
                      height: "100%",
                      pointerEvents: "none",
                    }}
                  >
                    {renderSuggestionOverlays(index + 1)}
                  </div>
                </div>

                {/* Page label */}
                <div
                  className="absolute -bottom-6 left-1/2 transform -translate-x-1/2 text-xs whitespace-nowrap"
                  style={{ color: "#484f58" }}
                >
                  Page {index + 1} of {numPages}
                </div>
              </div>
            ))}
          </div>
        </Document>
      </div>

      {/* Entity type popup */}
      {popupPosition && entityTypes.length > 0 && (
        <div
          ref={popupRef}
          className="dl-annotation-popup visible"
          style={{
            left: `${popupPosition.x}px`,
            top: `${popupPosition.y}px`,
          }}
        >
          {(() => {
            // Group entity types by parent
            const grouped: Record<string, typeof entityTypes> = {};
            entityTypes.forEach((et) => {
              const parts = et.name.split(".");
              const parent = parts.length > 1 ? parts[0] : "_root";
              if (!grouped[parent]) grouped[parent] = [];
              grouped[parent].push(et);
            });

            return Object.entries(grouped).map(([parent, types]) => (
              <div key={parent}>
                {parent !== "_root" && (
                  <div
                    style={{
                      fontSize: "11px",
                      color: "#8b949e",
                      fontWeight: 600,
                      padding: "4px 8px",
                      borderBottom: "1px solid #21262d",
                      marginTop: "4px",
                    }}
                  >
                    {parent}
                  </div>
                )}
                {types.map((et) => {
                  const displayName = et.name.split(".").pop() || et.name;
                  return (
                    <button
                      key={et.id}
                      className="dl-popup-entity-btn"
                      style={{
                        background: `${et.color}30`,
                        color: et.color,
                        borderColor: `${et.color}40`,
                      }}
                      onClick={() => applyFromPopup(et.id)}
                    >
                      {displayName}
                    </button>
                  );
                })}
              </div>
            ));
          })()}
        </div>
      )}
    </div>
  );
}
