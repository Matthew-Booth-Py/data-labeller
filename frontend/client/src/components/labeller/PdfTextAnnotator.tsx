/**
 * PdfTextAnnotator - Component for annotating PDFs with text selection
 * Renders the actual PDF and allows highlighting text to create annotations
 */

import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import { createPortal } from "react-dom";
import { Document, Page, pdfjs } from "react-pdf";
import { ZoomIn, ZoomOut, Loader2 } from "lucide-react";
import type {
  GroundTruthAnnotation,
  BoundingBoxData,
  AnnotationSuggestion,
} from "@/lib/api";
import { formatAnnotationValue } from "@/lib/utils";
import { BEAZLEY_PALETTE } from "@/theme/design-tokens";
import { alphaColor, getReadableTextColor } from "./annotationColors";
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

interface TablePreviewRow {
  rowNumber: number;
  values: Record<string, unknown>;
}

interface TablePreviewColumn {
  key: string;
  label: string;
  align?: "left" | "right";
}

interface TableOverlay {
  id: string;
  pageNum: number;
  groupName: string;
  label: string;
  color: string;
  leftPct: number;
  topPct: number;
  widthPct: number;
  heightPct: number;
  rows: TablePreviewRow[];
  columns: string[];
  totalRows: number;
  totalColumns: number;
}

const MAX_TABLE_PREVIEW_COLUMNS = 10;

function formatTableCellValue(value: unknown): string {
  const formatted = formatAnnotationValue(value, 0);
  return formatted || "—";
}

function prettifyTableColumnLabel(key: string): string {
  return key
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function parseHierarchyPath(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => String(item).trim())
      .filter(Boolean);
  }

  return String(value ?? "")
    .split(">")
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildSpreadsheetPreview(overlay: TableOverlay): {
  columns: TablePreviewColumn[];
  rows: Array<Record<string, string | number>>;
  hiddenColumnCount: number;
} {
  const columns: TablePreviewColumn[] = [];
  const consumedKeys = new Set<string>();

  if (overlay.columns.includes("hierarchy_path")) {
    columns.push({ key: "__section", label: "Section" });
    columns.push({ key: "__metric", label: "Metric" });
    consumedKeys.add("hierarchy_path");
  }

  for (const key of overlay.columns) {
    if (consumedKeys.has(key) || !key.endsWith("_value")) {
      continue;
    }

    const headerKey = key.replace(/_value$/, "_header");
    const headerLabel = overlay.rows
      .map((row) => row.values[headerKey])
      .find((value) => value !== null && value !== undefined && String(value).trim() !== "");

    columns.push({
      key,
      label: headerLabel ? String(headerLabel) : prettifyTableColumnLabel(key),
      align: "right",
    });
    consumedKeys.add(key);
    consumedKeys.add(headerKey);
  }

  for (const key of overlay.columns) {
    if (consumedKeys.has(key)) {
      continue;
    }

    columns.push({
      key,
      label: prettifyTableColumnLabel(key),
      align: key.includes("value") ? "right" : "left",
    });
  }

  const visibleColumns = columns.slice(0, MAX_TABLE_PREVIEW_COLUMNS);
  const rows = overlay.rows.map((row) => {
    const rowValues: Record<string, string | number> = {
      __row: row.rowNumber,
    };
    const hierarchyPath = parseHierarchyPath(row.values.hierarchy_path);

    if (visibleColumns.some((column) => column.key === "__section")) {
      rowValues.__section = hierarchyPath[0] ?? "—";
    }
    if (visibleColumns.some((column) => column.key === "__metric")) {
      rowValues.__metric =
        hierarchyPath.length > 1
          ? hierarchyPath.slice(1).join(" > ")
          : hierarchyPath[0] ?? "—";
    }

    for (const column of visibleColumns) {
      if (column.key.startsWith("__")) {
        continue;
      }
      rowValues[column.key] = formatTableCellValue(row.values[column.key]);
    }

    return rowValues;
  });

  return {
    columns: visibleColumns,
    rows,
    hiddenColumnCount: Math.max(columns.length - visibleColumns.length, 0),
  };
}

function getFieldGroupName(fieldName: string): string {
  const [groupName] = fieldName.split(".");
  return groupName || fieldName;
}

function getFieldLeafName(fieldName: string): string {
  const parts = fieldName.split(".");
  return parts[parts.length - 1] || fieldName;
}

function formatGroupLabel(groupName: string): string {
  return groupName
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function getAnnotationInstanceNumber(
  annotation: GroundTruthAnnotation,
): number | null {
  const rawInstance = (
    annotation.annotation_data as { instance_num?: number | string }
  ).instance_num;
  const parsed =
    typeof rawInstance === "number" ? rawInstance : Number(rawInstance);
  return Number.isFinite(parsed) && parsed >= 1 ? parsed : null;
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
  const [hoveredTableOverlayId, setHoveredTableOverlayId] = useState<
    string | null
  >(null);
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

  const tableOverlaysByPage = useMemo(() => {
    const groupRows = new Map<
      string,
      {
        columns: string[];
        rows: Map<number, Record<string, unknown>>;
      }
    >();
    const pageOverlays = new Map<
      string,
      {
        pageNum: number;
        groupName: string;
        color: string;
        minX: number;
        minY: number;
        maxX: number;
        maxY: number;
      }
    >();

    annotations.forEach((annotation) => {
      if (annotation.annotation_type !== "bbox") return;
      if (!annotation.field_name.includes(".")) return;

      const bboxData = annotation.annotation_data as BoundingBoxData;
      const bbox = normalizeBBox(bboxData);
      const pageNum = getAnnotationPage(annotation);
      const instanceNum = Number(
        (bboxData as { instance_num?: number | string }).instance_num,
      );

      if (!bbox || !pageNum || !Number.isFinite(instanceNum) || instanceNum < 1) {
        return;
      }

      const groupName = getFieldGroupName(annotation.field_name);
      const leafName = getFieldLeafName(annotation.field_name);
      const groupState = groupRows.get(groupName) ?? {
        columns: [],
        rows: new Map<number, Record<string, unknown>>(),
      };
      if (!groupState.columns.includes(leafName)) {
        groupState.columns.push(leafName);
      }
      groupState.rows.set(instanceNum, {
        ...(groupState.rows.get(instanceNum) ?? {}),
        [leafName]: annotation.value,
      });
      groupRows.set(groupName, groupState);

      const overlayKey = `${pageNum}:${groupName}`;
      const existingOverlay = pageOverlays.get(overlayKey);
      const nextBounds = {
        pageNum,
        groupName,
        color: getEntityColor(annotation.field_name),
        minX: existingOverlay ? Math.min(existingOverlay.minX, bbox.x) : bbox.x,
        minY: existingOverlay ? Math.min(existingOverlay.minY, bbox.y) : bbox.y,
        maxX: existingOverlay
          ? Math.max(existingOverlay.maxX, bbox.x + bbox.width)
          : bbox.x + bbox.width,
        maxY: existingOverlay
          ? Math.max(existingOverlay.maxY, bbox.y + bbox.height)
          : bbox.y + bbox.height,
      };
      pageOverlays.set(overlayKey, nextBounds);
    });

    const overlaysByPage: Record<number, TableOverlay[]> = {};
    pageOverlays.forEach((overlayState, overlayKey) => {
      const previewState = groupRows.get(overlayState.groupName);
      if (!previewState) return;

      const orderedColumns = previewState.columns;
      const sortedRows = Array.from(previewState.rows.entries())
        .sort((a, b) => a[0] - b[0])
        .map(([rowNumber, values]) => ({ rowNumber, values }));

      if (orderedColumns.length === 0 || sortedRows.length === 0) {
        return;
      }

      const overlay: TableOverlay = {
        id: overlayKey,
        pageNum: overlayState.pageNum,
        groupName: overlayState.groupName,
        label: formatGroupLabel(overlayState.groupName),
        color: overlayState.color,
        leftPct: overlayState.minX,
        topPct: overlayState.minY,
        widthPct: Math.max(overlayState.maxX - overlayState.minX, 1.2),
        heightPct: Math.max(overlayState.maxY - overlayState.minY, 1.2),
        rows: sortedRows,
        columns: orderedColumns,
        totalRows: sortedRows.length,
        totalColumns: orderedColumns.length,
      };

      if (!overlaysByPage[overlay.pageNum]) {
        overlaysByPage[overlay.pageNum] = [];
      }
      overlaysByPage[overlay.pageNum]?.push(overlay);
    });

    Object.values(overlaysByPage).forEach((overlays) => {
      overlays.sort((a, b) => {
        const areaA = a.widthPct * a.heightPct;
        const areaB = b.widthPct * b.heightPct;
        return areaA - areaB;
      });
    });

    return overlaysByPage;
  }, [annotations, getAnnotationPage, getEntityColor, normalizeBBox]);

  useEffect(() => {
    setHoveredTableOverlayId(null);
  }, [documentId, annotations]);

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
              rects.reduce(
                (max, r) => Math.max(max, r.leftPct + r.widthPct),
                0,
              ) - rects[0].leftPct,
            height:
              rects.reduce(
                (max, r) => Math.max(max, r.topPct + r.heightPct),
                0,
              ) - rects[0].topPct,
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

  // Close popup when clicking outside both the popup and the PDF viewer (e.g. sidebar).
  // Clicks inside the PDF area do not close the popup so labels stay visible while working in the doc.
  const handleMouseDown = useCallback((e: MouseEvent) => {
    const target = e.target as Node;
    if (popupRef.current?.contains(target)) return;
    if (containerRef.current?.contains(target)) return;
    setPopupPosition(null);
    setPendingSelection(null);
    latestSelectionRef.current = null;
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
        a.annotation_type === "bbox" &&
        getAnnotationPage(a) === pageNum &&
        !(
          a.field_name.includes(".") &&
          getAnnotationInstanceNumber(a) !== null
        ),
    );

    return pageAnnotations.map((ann) => {
      const bboxData = ann.annotation_data as BoundingBoxData;
      const bbox = normalizeBBox(bboxData);
      if (!bbox) return null;
      const color = getEntityColor(ann.field_name);
      const labelTextColor = getReadableTextColor(color);
      const inactiveBadgeBackground = alphaColor(color, 0.18);
      const inactiveBadgeTextColor = getReadableTextColor(
        inactiveBadgeBackground,
      );
      const label = ann.field_name.split(".").pop() || ann.field_name;

      // Build tooltip with row number if available
      const instanceNum = getAnnotationInstanceNumber(ann);
      const hasRow = instanceNum !== null;
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
                color: isActiveRow ? labelTextColor : inactiveBadgeTextColor,
                background: isActiveRow ? color : inactiveBadgeBackground,
              }}
            >
              {instanceNum}
            </div>
          )}
          <div
            className="dl-overlay-label"
            style={{
              background: color,
              color: labelTextColor,
              borderColor: alphaColor(color, 0.5),
            }}
          >
            {label}
            {hasRow ? ` #${instanceNum}` : ""}
          </div>
        </div>
      );
    });
  };

  const renderTableOverlays = (pageNum: number) => {
    const overlays = tableOverlaysByPage[pageNum] ?? [];

    return overlays.map((overlay) => {
      const isHovered = hoveredTableOverlayId === overlay.id;
      const labelTextColor = getReadableTextColor(overlay.color);
      const preview = buildSpreadsheetPreview(overlay);
      const hiddenRowCount = 0;
      const hiddenColumnCount = preview.hiddenColumnCount;

      return (
        <div
          key={overlay.id}
          className={`dl-table-hover-overlay ${isHovered ? "active" : ""}`}
          style={{
            left: `${overlay.leftPct}%`,
            top: `${overlay.topPct}%`,
            width: `${overlay.widthPct}%`,
            height: `${overlay.heightPct}%`,
            backgroundColor: alphaColor(overlay.color, isHovered ? 0.22 : 0.12),
            borderColor: alphaColor(overlay.color, isHovered ? 0.88 : 0.6),
            boxShadow: isHovered
              ? `0 0 0 2px ${alphaColor(overlay.color, 0.2)}`
              : undefined,
          }}
        >
          <div
            className="dl-table-hover-label"
            style={{ background: overlay.color, color: labelTextColor }}
          >
            {overlay.label}
            <span className="dl-table-hover-label-meta">
              {overlay.totalRows} row{overlay.totalRows === 1 ? "" : "s"}
            </span>
          </div>

          {isHovered && (
            <div className="dl-table-preview">
              <div className="dl-table-preview-header">
                <div>
                  <div className="dl-table-preview-title">
                    Extracted table
                  </div>
                  <div className="dl-table-preview-subtitle">
                    {overlay.label}
                  </div>
                </div>
                <div className="dl-table-preview-meta">
                  Page {overlay.pageNum}
                </div>
              </div>

              <div className="dl-table-preview-scroll">
                <table className="dl-table-preview-table">
                  <thead>
                    <tr>
                      <th>Row</th>
                      {preview.columns.map((column) => (
                        <th
                          key={`${overlay.id}-${column.key}`}
                          className={
                            column.key === "__section"
                              ? "dl-table-preview-col-section"
                              : column.key === "__metric"
                                ? "dl-table-preview-col-metric"
                                : column.align === "right"
                                  ? "dl-table-preview-col-value"
                                  : undefined
                          }
                        >
                          {column.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((row: any) => (
                      <tr key={`${overlay.id}-row-${row.__row}`}>
                        <td className="dl-table-preview-rownum">{row.__row}</td>
                        {false && preview.columns.map((column: any) => (
                          <td
                            key={`${overlay.id}-${row.__row}-${column.key}`}
                            className={
                              column.key === "__section"
                                ? "dl-table-preview-col-section"
                                : column.key === "__metric"
                                  ? "dl-table-preview-col-metric"
                                  : column.align === "right"
                                    ? "dl-table-preview-col-value"
                                    : undefined
                            }
                          >
                            {row.values[column] || "—"}
                          </td>
                        ))}
                        {preview.columns.map((column) => (
                          <td
                            key={`${overlay.id}-${row.__row}-${column.key}-preview`}
                            className={
                              column.key === "__section"
                                ? "dl-table-preview-col-section"
                                : column.key === "__metric"
                                  ? "dl-table-preview-col-metric"
                                  : column.align === "right"
                                    ? "dl-table-preview-col-value"
                                    : undefined
                            }
                          >
                            {String(row[column.key] ?? "—")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {hiddenColumnCount > 0 && (
                <div className="dl-table-preview-footnote">
                  {`+${hiddenColumnCount} more column${hiddenColumnCount === 1 ? "" : "s"}`}
                  {hiddenRowCount > 0 && hiddenColumnCount > 0 ? " • " : null}
                  {hiddenColumnCount > 0
                    ? `+${hiddenColumnCount} more column${hiddenColumnCount === 1 ? "" : "s"}`
                    : null}
                </div>
              )}
            </div>
          )}
        </div>
      );
    });
  };

  const handlePageMouseMove = useCallback(
    (pageNum: number, event: React.MouseEvent<HTMLDivElement>) => {
      const overlays = tableOverlaysByPage[pageNum] ?? [];
      if (overlays.length === 0) {
        if (hoveredTableOverlayId !== null) {
          setHoveredTableOverlayId(null);
        }
        return;
      }

      const pageRect = event.currentTarget.getBoundingClientRect();
      if (pageRect.width === 0 || pageRect.height === 0) {
        return;
      }

      const xPct = ((event.clientX - pageRect.left) / pageRect.width) * 100;
      const yPct = ((event.clientY - pageRect.top) / pageRect.height) * 100;
      const hoveredOverlay =
        overlays.find(
          (overlay) =>
            xPct >= overlay.leftPct &&
            xPct <= overlay.leftPct + overlay.widthPct &&
            yPct >= overlay.topPct &&
            yPct <= overlay.topPct + overlay.heightPct,
        ) ?? null;

      const nextId = hoveredOverlay?.id ?? null;
      if (nextId !== hoveredTableOverlayId) {
        setHoveredTableOverlayId(nextId);
      }
    },
    [hoveredTableOverlayId, tableOverlaysByPage],
  );

  // Render suggestion overlays on a page
  const renderSuggestionOverlays = (pageNum: number) => {
    const pageSuggestions = suggestions.filter((s) => {
      if (s.annotation_type !== "bbox") return false;
      const rawPage = (s.annotation_data as { page?: unknown })?.page;
      const parsedPage =
        typeof rawPage === "number" ? rawPage : Number(rawPage);
      return Number.isFinite(parsedPage) && parsedPage === pageNum;
    });

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
                Labelling as <strong>{activeEntityType.name}</strong> —
                highlight text to annotate
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
                  maxPageAnnotationCount > 0
                    ? count / maxPageAnnotationCount
                    : 0;
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
                <div
                  key={`page_${index + 1}`}
                  className="relative dl-viewer-surface"
                  onMouseMove={(event) => handlePageMouseMove(index + 1, event)}
                  onMouseLeave={() => setHoveredTableOverlayId(null)}
                >
                  <Page
                    pageNumber={index + 1}
                    scale={scale}
                    renderTextLayer={true}
                    renderAnnotationLayer={false}
                  />

                  {showTableGrid && (
                    <div className="dl-table-grid-overlay absolute inset-0 z-[9] pointer-events-none" />
                  )}

                  <div className="absolute inset-0 z-[9] pointer-events-none overflow-visible">
                    {renderTableOverlays(index + 1)}
                  </div>

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

      {/* Entity type popup — portaled to body so position:fixed is viewport-stable regardless of hover area */}
      {popupPosition &&
        popupEntityTypes.length > 0 &&
        createPortal(
          <div
            ref={popupRef}
            className="dl-annotation-popup visible"
            style={{
              left: `${popupPosition.x}px`,
              top: `${popupPosition.y}px`,
            }}
          >
            {(() => {
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
                            /* Opaque tint so button text is readable over document */
                            background: `${et.color}E6`,
                            color: "#ffffff",
                            border: `1px solid ${et.color}99`,
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
          </div>,
          document.body,
        )}
    </div>
  );
}
