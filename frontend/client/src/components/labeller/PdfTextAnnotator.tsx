/**
 * PdfTextAnnotator - Component for annotating PDFs with text selection
 * Renders the actual PDF and allows highlighting text to create annotations
 */

import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { ZoomIn, ZoomOut, Loader2 } from "lucide-react";
import type {
  GroundTruthAnnotation,
  BoundingBoxData,
  AnnotationSuggestion,
} from "@/lib/api";
import { BEAZLEY_PALETTE } from "@/theme/design-tokens";
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
  activeRowNumber?: number;
  showTableGrid?: boolean;
  forceFieldChooser?: boolean;
  preferredFieldIds?: string[];
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

interface SelectionExtraction {
  pending: PendingSelection;
  popup: {
    x: number;
    y: number;
  };
}

interface SelectionSnapshot extends SelectionExtraction {
  capturedAt: number;
}

export function PdfTextAnnotator({
  documentId,
  pdfUrl,
  annotations,
  entityTypes,
  activeEntityTypeId,
  activeRowNumber = 1,
  showTableGrid = false,
  forceFieldChooser = false,
  preferredFieldIds = [],
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
  const [currentPage, setCurrentPage] = useState(1);
  const [pendingSelection, setPendingSelection] =
    useState<PendingSelection | null>(null);
  const [popupPosition, setPopupPosition] = useState<{
    x: number;
    y: number;
  } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const hasAutoScrolledToAnnotationRef = useRef(false);
  const latestSelectionRef = useRef<SelectionSnapshot | null>(null);

  // Get active entity type
  const activeEntityType = entityTypes.find(
    (et) => et.id === activeEntityTypeId,
  );

  const popupEntityTypes = useMemo(() => {
    if (preferredFieldIds.length === 0) return entityTypes;
    const rank = new Map(preferredFieldIds.map((id, index) => [id, index]));
    return [...entityTypes].sort((a, b) => {
      const rankA = rank.has(a.id) ? rank.get(a.id)! : Number.MAX_SAFE_INTEGER;
      const rankB = rank.has(b.id) ? rank.get(b.id)! : Number.MAX_SAFE_INTEGER;
      if (rankA !== rankB) return rankA - rankB;
      return a.name.localeCompare(b.name);
    });
  }, [entityTypes, preferredFieldIds]);

  // Handle PDF load success
  const onDocumentLoadSuccess = useCallback(
    ({ numPages }: { numPages: number }) => {
      setNumPages(numPages);
      setCurrentPage(1);
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
      return et?.color || BEAZLEY_PALETTE.light;
    },
    [entityTypes],
  );

  const getAnnotationPage = useCallback((annotation: GroundTruthAnnotation) => {
    const rawPage = (annotation.annotation_data as { page?: unknown })?.page;
    const parsedPage = typeof rawPage === "number" ? rawPage : Number(rawPage);

    if (!Number.isFinite(parsedPage) || parsedPage < 1) {
      return null;
    }

    return parsedPage;
  }, []);

  const normalizeBBox = useCallback(
    (rawData: BoundingBoxData | Record<string, unknown>) => {
      const x = Number((rawData as { x?: unknown }).x);
      const y = Number((rawData as { y?: unknown }).y);
      const width = Number((rawData as { width?: unknown }).width);
      const height = Number((rawData as { height?: unknown }).height);

      if (
        !Number.isFinite(x) ||
        !Number.isFinite(y) ||
        !Number.isFinite(width) ||
        !Number.isFinite(height)
      ) {
        return null;
      }

      return { x, y, width, height };
    },
    [],
  );

  const scrollToPage = useCallback((pageNum: number) => {
    const pageEl = containerRef.current?.querySelector(
      `.react-pdf__Page[data-page-number="${pageNum}"]`,
    ) as HTMLElement | null;
    if (pageEl) {
      pageEl.scrollIntoView({ behavior: "smooth", block: "center" });
      setCurrentPage(pageNum);
    }
  }, []);

  const annotationCountsByPage = useMemo(() => {
    const counts: Record<number, number> = {};
    annotations
      .filter((annotation) => annotation.annotation_type === "bbox")
      .forEach((annotation) => {
        const page = getAnnotationPage(annotation);
        if (!page) return;
        counts[page] = (counts[page] || 0) + 1;
      });
    return counts;
  }, [annotations, getAnnotationPage]);

  const maxPageAnnotationCount = useMemo(() => {
    const values = Object.values(annotationCountsByPage);
    return values.length > 0 ? Math.max(...values) : 0;
  }, [annotationCountsByPage]);

  useEffect(() => {
    hasAutoScrolledToAnnotationRef.current = false;
  }, [documentId]);

  useEffect(() => {
    if (
      isLoading ||
      numPages === 0 ||
      hasAutoScrolledToAnnotationRef.current ||
      annotations.length === 0
    ) {
      return;
    }

    const pageCounts = new Map<number, number>();
    for (const page of annotations
      .filter((annotation) => annotation.annotation_type === "bbox")
      .map((annotation) => getAnnotationPage(annotation))
      .filter((page): page is number => page !== null)) {
      pageCounts.set(page, (pageCounts.get(page) || 0) + 1);
    }

    const targetPage = Array.from(pageCounts.entries()).sort((a, b) => {
      if (b[1] !== a[1]) return b[1] - a[1];
      return a[0] - b[0];
    })[0]?.[0];

    if (!targetPage || targetPage <= 1) {
      hasAutoScrolledToAnnotationRef.current = true;
      return;
    }

    requestAnimationFrame(() => {
      scrollToPage(targetPage);
    });

    hasAutoScrolledToAnnotationRef.current = true;
  }, [annotations, getAnnotationPage, isLoading, numPages, scrollToPage]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || numPages === 0) return;

    const handleScroll = () => {
      const pages = Array.from(
        container.querySelectorAll(".react-pdf__Page"),
      ) as HTMLElement[];
      if (pages.length === 0) return;

      const viewportCenter = container.getBoundingClientRect().top + 240;
      let nearestPage = currentPage;
      let nearestDistance = Number.POSITIVE_INFINITY;

      pages.forEach((pageElement) => {
        const top = pageElement.getBoundingClientRect().top;
        const distance = Math.abs(top - viewportCenter);
        const page = Number(pageElement.dataset.pageNumber || "1");
        if (distance < nearestDistance) {
          nearestDistance = distance;
          nearestPage = page;
        }
      });

      if (nearestPage !== currentPage) {
        setCurrentPage(nearestPage);
      }
    };

    container.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => {
      container.removeEventListener("scroll", handleScroll);
    };
  }, [currentPage, numPages]);

  const extractSelection = useCallback(
    (selection: Selection | null): SelectionExtraction | null => {
      if (!selection || selection.isCollapsed || !selection.rangeCount) {
        return null;
      }

      const range = selection.getRangeAt(0);
      const startElement =
        range.startContainer instanceof Element
          ? range.startContainer
          : range.startContainer.parentElement;
      const endElement =
        range.endContainer instanceof Element
          ? range.endContainer
          : range.endContainer.parentElement;

      if (!startElement || !endElement) {
        return null;
      }

      const startPage = startElement.closest(".react-pdf__Page");
      const endPage = endElement.closest(".react-pdf__Page");
      if (!startPage || !endPage || startPage !== endPage) {
        return null;
      }

      if (
        !startElement.closest(".react-pdf__Page__textContent") ||
        !endElement.closest(".react-pdf__Page__textContent")
      ) {
        return null;
      }

      const selectedText = selection.toString().trim();
      if (!selectedText) {
        return null;
      }

      const pageNum = Number.parseInt(
        startPage.getAttribute("data-page-number") || "1",
        10,
      );
      if (!Number.isFinite(pageNum) || pageNum < 1) {
        return null;
      }

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
        return null;
      }

      const rect = range.getBoundingClientRect();
      return {
        pending: { pageNum, text: selectedText, rects },
        popup: {
          x: Math.min(rect.left, window.innerWidth - 420),
          y: rect.bottom + 8,
        },
      };
    },
    [],
  );

  useEffect(() => {
    const handleSelectionChange = () => {
      const extracted = extractSelection(window.getSelection());
      if (!extracted) return;
      latestSelectionRef.current = {
        ...extracted,
        capturedAt: Date.now(),
      };
    };

    document.addEventListener("selectionchange", handleSelectionChange);
    return () => {
      document.removeEventListener("selectionchange", handleSelectionChange);
    };
  }, [extractSelection]);

  // Handle text selection
  const handleMouseUp = useCallback(
    (event: MouseEvent) => {
      const targetNode = event.target as Node | null;

      // Let the browser finalize text selection before reading range rects.
      requestAnimationFrame(() => {
        if (targetNode && popupRef.current?.contains(targetNode)) {
          return;
        }

        const liveSelection = extractSelection(window.getSelection());
        const cachedSelection =
          latestSelectionRef.current &&
          Date.now() - latestSelectionRef.current.capturedAt <= 500
            ? latestSelectionRef.current
            : null;
        const extracted = liveSelection || cachedSelection;

        if (!extracted) {
          setPopupPosition(null);
          setPendingSelection(null);
          latestSelectionRef.current = null;
          return;
        }

        const {
          pending: { pageNum, text, rects },
          popup,
        } = extracted;

        // If active entity type and inline chooser is off, apply directly.
        if (activeEntityTypeId && activeEntityType && !forceFieldChooser) {
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
            text: text,
          };
          onAnnotationCreate(activeEntityType.name, text, bbox);
          window.getSelection()?.removeAllRanges();
          setPopupPosition(null);
          setPendingSelection(null);
          latestSelectionRef.current = null;
          return;
        }

        // Show popup to pick entity type
        if (popupEntityTypes.length === 0) {
          return;
        }

        setPendingSelection({ pageNum, text, rects });
        setPopupPosition(popup);
      });
    },
    [
      extractSelection,
      activeEntityTypeId,
      activeEntityType,
      forceFieldChooser,
      onAnnotationCreate,
      popupEntityTypes.length,
    ],
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
      latestSelectionRef.current = null;
    },
    [pendingSelection, entityTypes, onAnnotationCreate],
  );

  // Close popup on outside click
  const handleMouseDown = useCallback((e: MouseEvent) => {
    if (popupRef.current && !popupRef.current.contains(e.target as Node)) {
      setPopupPosition(null);
      setPendingSelection(null);
      latestSelectionRef.current = null;
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
        latestSelectionRef.current = null;
      }

      // Enter confirms pending popup selection.
      if (e.key === "Enter" && pendingSelection) {
        const targetEntityId =
          activeEntityTypeId || popupEntityTypes[0]?.id || null;
        if (targetEntityId) {
          applyFromPopup(targetEntityId);
          e.preventDefault();
        }
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
    // Use capture so PDF.js/React handlers cannot swallow the event before we process selection.
    document.addEventListener("mouseup", handleMouseUp, true);
    document.addEventListener("mousedown", handleMouseDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mouseup", handleMouseUp, true);
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
    applyFromPopup,
    pendingSelection,
    popupEntityTypes,
  ]);

  // Render annotation highlights on a page
  const renderAnnotationHighlights = (pageNum: number) => {
    const pageAnnotations = annotations.filter(
      (a) =>
        a.annotation_type === "bbox" && getAnnotationPage(a) === pageNum,
    );

    return pageAnnotations.map((ann) => {
      const bboxData = ann.annotation_data as BoundingBoxData;
      const bbox = normalizeBBox(bboxData);
      if (!bbox) return null;
      const color = getEntityColor(ann.field_name);
      const label = ann.field_name.split(".").pop() || ann.field_name;

      // Build tooltip with row number if available
      const instanceNum = Number(
        (bboxData as { instance_num?: number | string }).instance_num,
      );
      const hasRow = Number.isFinite(instanceNum);
      const isActiveRow = hasRow && instanceNum === activeRowNumber;
      const tooltipText = hasRow
        ? `Row ${instanceNum} | Field ${ann.field_name} | "${bboxData.text || ann.value}"\nClick to delete`
        : `Field ${ann.field_name} | "${bboxData.text || ann.value}"\nClick to delete`;

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
            backgroundColor: isActiveRow ? `${color}66` : `${color}33`,
            border: `1.5px solid ${color}`,
            borderRadius: "3px",
            boxShadow: isActiveRow ? `0 0 0 1.5px ${color}80` : undefined,
          }}
          onClick={() => onAnnotationDelete(ann.id)}
          title={tooltipText}
        >
          {hasRow && (
            <div
              className={`dl-row-margin-badge ${isActiveRow ? "active" : ""}`}
              style={{
                borderColor: color,
                color: isActiveRow ? BEAZLEY_PALETTE.dark : color,
                background: isActiveRow ? color : "#ffffff",
              }}
            >
              {instanceNum}
            </div>
          )}
          <div
            className="dl-overlay-label"
            style={{ background: color, color: BEAZLEY_PALETTE.dark }}
          >
            {label}
            {hasRow ? ` #${instanceNum}` : ""}
          </div>
        </div>
      );
    });
  };

  // Render suggestion overlays on a page
  const renderSuggestionOverlays = (pageNum: number) => {
    const pageSuggestions = suggestions.filter(
      (s) => {
        if (s.annotation_type !== "bbox") return false;
        const rawPage = (s.annotation_data as { page?: unknown })?.page;
        const parsedPage = typeof rawPage === "number" ? rawPage : Number(rawPage);
        return Number.isFinite(parsedPage) && parsedPage === pageNum;
      },
    );

    return pageSuggestions.map((suggestion) => {
      const bbox = normalizeBBox(suggestion.annotation_data as BoundingBoxData);
      if (!bbox) return null;
      const label =
        suggestion.field_name.split(".").pop() || suggestion.field_name;

      return (
        <div
          key={suggestion.id}
          className="absolute pointer-events-auto group dl-suggestion-box"
          style={{
            left: `${bbox.x}%`,
            top: `${bbox.y}%`,
            width: `${bbox.width}%`,
            height: `${bbox.height}%`,
          }}
          title={`AI suggestion (${Math.round((suggestion.confidence || 0) * 100)}%): ${suggestion.field_name}\n"${suggestion.value}"`}
        >
          {/* Label tag */}
          <div className="dl-overlay-label dl-suggestion-label">
            ✦ {label}
            <span className="dl-suggestion-confidence">
              {Math.round((suggestion.confidence || 0) * 100)}%
            </span>
            <button
              type="button"
              onClick={() => onSuggestionApprove?.(suggestion)}
              className="dl-popup-action approve"
              title="Approve"
            >
              ✓
            </button>
            <button
              type="button"
              onClick={() => onSuggestionReject?.(suggestion.id)}
              className="dl-popup-action reject"
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
    <div className="dl-viewer flex h-full min-h-0 flex-col">
      {/* Toolbar */}
      <div className="dl-toolbar justify-between">
        <div className="dl-toolbar-info flex items-center gap-2">
          {activeEntityType ? (
            <>
              <span
                className="w-3 h-3 rounded-full"
                style={{ background: activeEntityType.color }}
              />
              <span>
                Labelling as <strong>{activeEntityType.name}</strong>{" "}
                — highlight text to annotate
              </span>
            </>
          ) : entityTypes.length === 0 ? (
            <span>Add entity types in the sidebar to begin labelling</span>
          ) : (
            <span>Select an entity type, then highlight text to label it</span>
          )}
          <span className="dl-viewer-hint">
            Page {numPages === 0 ? "—" : `${currentPage}/${numPages}`}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="dl-btn dl-btn-sm"
            onClick={() => setScale((s) => Math.max(0.5, s - 0.25))}
          >
            <ZoomOut size={14} />
          </button>
          <span className="dl-zoom-value">{Math.round(scale * 100)}%</span>
          <button
            type="button"
            className="dl-btn dl-btn-sm"
            onClick={() => setScale((s) => Math.min(4.0, s + 0.25))}
          >
            <ZoomIn size={14} />
          </button>
        </div>
      </div>

      {/* PDF Viewer */}
      <Document
        file={pdfUrl}
        className="flex min-h-0 flex-1 overflow-hidden"
        onLoadSuccess={onDocumentLoadSuccess}
        onLoadError={onDocumentLoadError}
        loading={
          <div className="dl-viewer-loading flex h-96 flex-col items-center justify-center gap-3">
            <Loader2 className="dl-accent-icon h-8 w-8 animate-spin" />
            <span>Loading PDF...</span>
          </div>
        }
        error={
          <div className="flex flex-col items-center justify-center h-96 gap-3">
            <span className="text-5xl opacity-30">⚠️</span>
            <span className="dl-viewer-error">Failed to load PDF</span>
            <span className="dl-viewer-error-muted text-xs">{error}</span>
          </div>
        }
      >
        <div className="flex min-h-0 flex-1 overflow-hidden">
          <aside className="dl-page-nav flex flex-col w-[100px] lg:w-[130px] shrink-0 border-r border-[var(--dl-border)] bg-[var(--dl-bg-secondary)]">
            <div className="dl-page-nav-scroll flex-1 space-y-2 overflow-y-auto p-2">
              {Array.from(new Array(numPages), (_, index) => {
                const pageNum = index + 1;
                const count = annotationCountsByPage[pageNum] || 0;
                const intensity =
                  maxPageAnnotationCount > 0 ? count / maxPageAnnotationCount : 0;
                return (
                  <button
                    key={`nav-page-${pageNum}`}
                    type="button"
                    className={`dl-page-nav-item ${currentPage === pageNum ? "active" : ""}`}
                    onClick={() => scrollToPage(pageNum)}
                  >
                    <div className="dl-page-thumb">
                      <Page
                        pageNumber={pageNum}
                        width={78}
                        renderTextLayer={false}
                        renderAnnotationLayer={false}
                      />
                    </div>
                    <div className="flex items-center justify-between text-[10px] text-[var(--dl-text-muted)]">
                      <span>P{pageNum}</span>
                      <span
                        className="rounded-full px-1.5 py-0.5"
                        style={{
                          backgroundColor:
                            count > 0
                              ? `rgba(217, 26, 166, ${0.18 + intensity * 0.5})`
                              : "transparent",
                        }}
                      >
                        {count}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
            <div className="border-t border-[var(--dl-border)] p-2">
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.05em] text-[var(--dl-text-subtle)]">
                Annotation Heatmap
              </div>
              <div className="flex gap-1">
                {Array.from(new Array(numPages), (_, index) => {
                  const pageNum = index + 1;
                  const count = annotationCountsByPage[pageNum] || 0;
                  const intensity =
                    maxPageAnnotationCount > 0
                      ? count / maxPageAnnotationCount
                      : 0;
                  return (
                    <button
                      key={`heat-${pageNum}`}
                      type="button"
                      className="h-6 flex-1 rounded-sm border border-[var(--dl-border)] transition-transform hover:-translate-y-px"
                      style={{
                        backgroundColor:
                          count > 0
                            ? `rgba(217, 26, 166, ${0.12 + intensity * 0.55})`
                            : "rgba(79, 2, 89, 0.06)",
                      }}
                      title={`Page ${pageNum}: ${count} annotation${count === 1 ? "" : "s"}`}
                      onClick={() => scrollToPage(pageNum)}
                    />
                  );
                })}
              </div>
            </div>
          </aside>

          <div ref={containerRef} className="dl-viewer flex-1 overflow-auto">
            <div className="flex flex-col items-center gap-4 p-6">
              {Array.from(new Array(numPages), (_, index) => (
                <div key={`page_${index + 1}`} className="relative dl-viewer-surface">
                  <Page
                    pageNumber={index + 1}
                    scale={scale}
                    renderTextLayer={true}
                    renderAnnotationLayer={false}
                  />

                  {showTableGrid && (
                    <div className="dl-table-grid-overlay absolute inset-0 z-[9] pointer-events-none" />
                  )}

                  {/* Annotation overlay */}
                  <div className="absolute inset-0 z-10 pointer-events-none overflow-visible">
                    {renderAnnotationHighlights(index + 1)}
                  </div>

                  {/* Suggestion overlay */}
                  <div className="absolute inset-0 z-[11] pointer-events-none overflow-visible">
                    <div className="relative h-full w-full pointer-events-none">
                      {renderSuggestionOverlays(index + 1)}
                    </div>
                  </div>

                  {/* Page label */}
                  <div className="dl-viewer-page-label absolute right-3 top-3 z-20 whitespace-nowrap">
                    Page {index + 1} of {numPages}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Document>

      {/* Entity type popup */}
      {popupPosition && popupEntityTypes.length > 0 && (
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
            const grouped: Record<string, typeof popupEntityTypes> = {};
            popupEntityTypes.forEach((et) => {
              const parts = et.name.split(".");
              const parent = parts.length > 1 ? parts[0] : "_root";
              if (!grouped[parent]) grouped[parent] = [];
              grouped[parent].push(et);
            });

            return Object.entries(grouped).map(([parent, types]) => (
              <div key={parent} className="dl-popup-group">
                {parent !== "_root" && (
                  <div className="dl-popup-group-title">{parent}</div>
                )}
                <div className="dl-popup-group-buttons">
                  {types.map((et) => {
                    const displayName = et.name.split(".").pop() || et.name;
                    return (
                      <button
                        key={et.id}
                        type="button"
                        className="dl-popup-entity-btn"
                        style={{
                          background: `${et.color}30`,
                          color: et.color,
                          borderColor: `${et.color}66`,
                        }}
                        onClick={() => applyFromPopup(et.id)}
                      >
                        {displayName}
                      </button>
                    );
                  })}
                </div>
              </div>
            ));
          })()}
        </div>
      )}
    </div>
  );
}
