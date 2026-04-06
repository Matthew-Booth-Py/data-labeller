/**
 * DataLabellerV2 - Beazley-themed data labelling interface
 * Features:
 * - Text span selection for PDFs and text files
 * - Bounding box annotation for images
 * - Schema fields as entity types with auto-assigned colors
 * - Keyboard shortcuts for power users
 */

import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  api,
  type GroundTruthAnnotation,
  type TextSpanData,
  type BoundingBoxData,
  type AnnotationSuggestion,
  type AnnotationType,
} from "@/lib/api";
import {
  TextSpanAnnotator,
  type EntityType,
} from "@/components/labeller/TextSpanAnnotator";
import { PdfTextAnnotator } from "@/components/labeller/PdfTextAnnotator";
import { ImageBboxAnnotator } from "@/components/labeller/ImageBboxAnnotator";
import { toast } from "sonner";
import {
  Loader2,
  FileText,
  Image,
  Copy,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Table2,
  Trash2,
  Search,
  Check,
  X,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { formatAnnotationValue, cn } from "@/lib/utils";
import { BEAZLEY_PALETTE } from "@/theme/design-tokens";

// Neutral, high-contrast annotation palette (intentionally brand-agnostic)
const ENTITY_COLORS = [
  "#60A5FA", // blue
  "#34D399", // emerald
  "#FBBF24", // amber
  "#F87171", // red
  "#A78BFA", // violet
  "#2DD4BF", // teal
  "#FB923C", // orange
  "#F472B6", // pink
  "#93C5FD", // light blue
  "#86EFAC", // light green
];

interface DataLabellerV2Props {
  projectId?: string;
}

type LabellerSidebarMode = "expanded" | "hidden";

const MAX_ROW_NUM = 999;
const EMPTY_SCHEMA_FIELDS: any[] = [];
const LABELLER_SIDEBAR_MODE_STORAGE_KEY = "labeller:sidebar-mode";

const arraysEqual = (a: string[], b: string[]) =>
  a.length === b.length && a.every((value, index) => value === b[index]);

const setsEqual = (a: Set<string>, b: Set<string>) => {
  if (a.size !== b.size) return false;
  return Array.from(a).every((value) => b.has(value));
};

const isLabellerSidebarMode = (
  value: string | null,
): value is LabellerSidebarMode => value === "expanded" || value === "hidden";

export function DataLabellerV2({ projectId: projectIdProp }: DataLabellerV2Props) {
  const exportMenuRef = useRef<HTMLDivElement | null>(null);
  const [mounted, setMounted] = useState(false);

  // Initialize state with safe defaults
  const [projectId, setProjectId] = useState<string>(projectIdProp || "all");
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [activeEntityTypeId, setActiveEntityTypeId] = useState<string | null>(
    null,
  );
  const [activeInstanceNum, setActiveInstanceNum] = useState<number>(1);

  // Load from storage after mount
  useEffect(() => {
    try {
      const storedProjectId =
        projectIdProp || localStorage.getItem("selected-project") || "all";
      setProjectId(storedProjectId);

      const storedDocId = sessionStorage.getItem(
        `labeller-selected-doc-${storedProjectId}`,
      );
      if (storedDocId) {
        setSelectedDocId(storedDocId);
      }

      const storedEntityId = sessionStorage.getItem(
        `labeller-active-entity-${storedProjectId}`,
      );
      if (storedEntityId) {
        setActiveEntityTypeId(storedEntityId);
      }

      const storedRow = sessionStorage.getItem(
        `labeller-active-row-${storedProjectId}`,
      );
      if (storedRow) {
        const parsed = parseInt(storedRow, 10);
        if (Number.isFinite(parsed)) {
          setActiveInstanceNum(parsed);
        }
      }
    } catch (error) {
      console.error("Error loading from storage:", error);
    }

    setMounted(true);
  }, [projectIdProp]);

  const [exportMenuVisible, setExportMenuVisible] = useState(false);
  const [suggestions, setSuggestions] = useState<AnnotationSuggestion[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [fieldFilter, setFieldFilter] = useState("");
  const [autoAdvanceRow, setAutoAdvanceRow] = useState(true);
  const [inlineFieldSwitcher, setInlineFieldSwitcher] = useState(true);
  const [tableDetectionMode, setTableDetectionMode] = useState(false);
  const [selectedTemplateFields, setSelectedTemplateFields] = useState<
    string[]
  >([]);
  const [sidebarMode, setSidebarMode] = useState<LabellerSidebarMode>(() => {
    if (typeof window === "undefined") return "expanded";
    const stored = window.localStorage.getItem(
      LABELLER_SIDEBAR_MODE_STORAGE_KEY,
    );
    return stored === "hidden"
      ? "hidden"
      : isLabellerSidebarMode(stored)
        ? stored
        : "expanded";
  });
  const rowShortcutAwaitRef = useRef(false);
  const rowShortcutDigitsRef = useRef("");
  const rowShortcutTimerRef = useRef<number | null>(null);
  const sidebarVisible = sidebarMode !== "hidden";

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(LABELLER_SIDEBAR_MODE_STORAGE_KEY, sidebarMode);
  }, [sidebarMode]);

  const toggleSidebarVisibility = () => {
    setSidebarMode((current) => (current === "hidden" ? "expanded" : "hidden"));
  };

  // Fetch documents
  const { data: documentsData } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.listDocuments(),
  });

  const { data: projectData } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.getProject(projectId),
    enabled: !!projectId && projectId !== "all",
  });

  // Filter documents by project
  const documents = useMemo(() => {
    if (!documentsData?.documents || !projectId || projectId === "all") {
      return [];
    }

    try {
      const projectDocumentIds = projectData?.project?.document_ids || [];
      return documentsData.documents.filter((doc) =>
        projectDocumentIds.includes(doc.id),
      );
    } catch (error) {
      console.error("Error filtering documents:", error);
      return [];
    }
  }, [documentsData, projectData, projectId]);

  // Persist selected document
  useEffect(() => {
    if (selectedDocId) {
      sessionStorage.setItem(
        `labeller-selected-doc-${projectId}`,
        selectedDocId,
      );
    } else {
      sessionStorage.removeItem(`labeller-selected-doc-${projectId}`);
    }
  }, [selectedDocId, projectId]);

  // Persist active entity type
  useEffect(() => {
    if (activeEntityTypeId) {
      sessionStorage.setItem(
        `labeller-active-entity-${projectId}`,
        activeEntityTypeId,
      );
    } else {
      sessionStorage.removeItem(`labeller-active-entity-${projectId}`);
    }
  }, [activeEntityTypeId, projectId]);

  // Persist active row number
  useEffect(() => {
    sessionStorage.setItem(
      `labeller-active-row-${projectId}`,
      String(activeInstanceNum),
    );
  }, [activeInstanceNum, projectId]);

  // Get selected document
  const selectedDocument = documents.find((d) => d.id === selectedDocId);

  // Get schema fields from document type using a stable fallback reference
  const schemaFields =
    selectedDocument?.document_type?.schema_fields ?? EMPTY_SCHEMA_FIELDS;

  // Convert schema fields to entity types with colors
  const entityTypes: EntityType[] = useMemo(() => {
    type FlatField = { name: string; fieldKind: "table" | "leaf" };

    const flattenFields = (fields: any[], prefix = ""): FlatField[] => {
      const result: FlatField[] = [];
      for (const field of fields) {
        const path = prefix ? `${prefix}.${field.name}` : field.name;

        const isTableField =
          field.type === "array" &&
          (field.extraction_method === "retrieval_table" ||
            field.items?.type === "object");

        if (isTableField) {
          // Array of objects — include the parent as a selectable "table" field
          result.push({ name: path, fieldKind: "table" });
          const subProperties = field.items?.properties
            ? Object.entries(field.items.properties)
            : [];
          for (const [propName, propField] of subProperties) {
            result.push(
              ...flattenFields(
                [{ ...(propField as object), name: propName }],
                path,
              ),
            );
          }
        } else if (field.type === "object" && field.properties) {
          for (const [propName, propField] of Object.entries(
            field.properties,
          )) {
            result.push(
              ...flattenFields(
                [{ ...(propField as object), name: propName }],
                path,
              ),
            );
          }
        } else {
          result.push({ name: path, fieldKind: "leaf" });
        }
      }
      return result;
    };

    return flattenFields(schemaFields).map(({ name, fieldKind }, i) => ({
      id: name,
      name,
      color: ENTITY_COLORS[i % ENTITY_COLORS.length],
      fieldKind,
    }));
  }, [schemaFields]);

  const getGroupName = useCallback((fieldName: string) => {
    const parts = fieldName.split(".");
    return parts.length > 1 ? parts[0] : "_root";
  }, []);

  const getFieldLeafName = useCallback((fieldName: string) => {
    const parts = fieldName.split(".");
    return parts[parts.length - 1] || fieldName;
  }, []);

  const rowAwareFieldNames = useMemo(
    () => entityTypes.map((et) => et.name).filter((name) => name.includes(".")),
    [entityTypes],
  );

  const activeEntityType = useMemo(
    () => entityTypes.find((et) => et.id === activeEntityTypeId),
    [entityTypes, activeEntityTypeId],
  );

  const activeGroupName = useMemo(
    () => (activeEntityType ? getGroupName(activeEntityType.name) : null),
    [activeEntityType, getGroupName],
  );

  // Group entity types by parent for hierarchical display
  const groupedEntityTypes = useMemo(() => {
    const groups: Record<string, EntityType[]> = {};

    entityTypes.forEach((et) => {
      const group = getGroupName(et.name);
      if (!groups[group]) {
        groups[group] = [];
      }
      groups[group].push(et);
    });

    // Table fields with no sub-fields end up only in _root and get filtered
    // out there. Give each table entity its own named group so the header
    // button always renders even when the columns list is empty.
    entityTypes
      .filter((et) => et.fieldKind === "table")
      .forEach((et) => {
        if (!groups[et.name]) {
          groups[et.name] = [];
        }
      });

    return groups;
  }, [entityTypes, getGroupName]);

  const filteredGroupedEntityTypes = useMemo(() => {
    const query = fieldFilter.trim().toLowerCase();
    if (!query) return groupedEntityTypes;

    const filtered: Record<string, EntityType[]> = {};
    Object.entries(groupedEntityTypes).forEach(([groupName, types]) => {
      const matches = types.filter((type) => {
        const leaf = getFieldLeafName(type.name).toLowerCase();
        return (
          type.name.toLowerCase().includes(query) ||
          leaf.includes(query) ||
          groupName.toLowerCase().includes(query)
        );
      });

      if (matches.length > 0) {
        filtered[groupName] = matches;
      }
    });
    return filtered;
  }, [fieldFilter, getFieldLeafName, groupedEntityTypes]);

  const activeGroupFieldNames = useMemo(() => {
    if (!activeGroupName || activeGroupName === "_root") {
      return rowAwareFieldNames;
    }
    return rowAwareFieldNames.filter(
      (name) => getGroupName(name) === activeGroupName,
    );
  }, [activeGroupName, getGroupName, rowAwareFieldNames]);

  const effectiveTemplateFields = useMemo(() => {
    if (selectedTemplateFields.length > 0) return selectedTemplateFields;
    return activeGroupFieldNames;
  }, [selectedTemplateFields, activeGroupFieldNames]);

  // Keep schema collapsed by default; only active or filtered groups auto-expand.
  useEffect(() => {
    const next = new Set<string>();
    if (activeGroupName && activeGroupName !== "_root") {
      next.add(activeGroupName);
    }
    if (fieldFilter.trim()) {
      Object.keys(filteredGroupedEntityTypes)
        .filter((groupName) => groupName !== "_root")
        .forEach((groupName) => next.add(groupName));
    }
    setExpandedGroups((prev) => (setsEqual(prev, next) ? prev : next));
  }, [activeGroupName, fieldFilter, filteredGroupedEntityTypes]);

  // Keep template fields in sync with available row-aware fields.
  useEffect(() => {
    const available = new Set(rowAwareFieldNames);
    setSelectedTemplateFields((prev) => {
      const persisted = prev.filter((field) => available.has(field));
      const next = persisted.length > 0 ? persisted : activeGroupFieldNames;
      return arraysEqual(prev, next) ? prev : next;
    });
  }, [activeGroupFieldNames, rowAwareFieldNames]);

  // Fetch annotations for selected document
  const { data: annotationsData, refetch: refetchAnnotations } = useQuery({
    queryKey: ["annotations", selectedDocId],
    queryFn: () =>
      selectedDocId
        ? api.getGroundTruthAnnotations(selectedDocId)
        : Promise.resolve({ annotations: [], total: 0 }),
    enabled: !!selectedDocId,
  });

  const annotations = annotationsData?.annotations || [];

  // Create annotation mutation
  const createAnnotationMutation = useMutation({
    mutationFn: async (data: {
      fieldName: string;
      value: any;
      annotationData: TextSpanData | BoundingBoxData;
      annotationType: AnnotationType;
    }) => {
      if (!selectedDocId) throw new Error("No document selected");

      return api.createGroundTruthAnnotation(selectedDocId, {
        document_id: selectedDocId,
        field_name: data.fieldName,
        value: data.value,
        annotation_type: data.annotationType,
        annotation_data: data.annotationData,
        labeled_by: "manual",
      });
    },
    onSuccess: () => {
      refetchAnnotations();
      toast.success("Annotation created");
    },
    onError: (error: Error) => {
      toast.error(`Failed to create annotation: ${error.message}`);
    },
  });

  // Delete annotation mutation
  const deleteAnnotationMutation = useMutation({
    mutationFn: async (annotationId: string) => {
      if (!selectedDocId) throw new Error("No document selected");
      return api.deleteGroundTruthAnnotation(selectedDocId, annotationId);
    },
    onSuccess: () => {
      refetchAnnotations();
      toast.success("Annotation deleted");
    },
    onError: (error: Error) => {
      toast.error(`Failed to delete annotation: ${error.message}`);
    },
  });

  // Handle annotation creation
  // After a table-level bbox is drawn, automatically extract the table contents
  // from that region via the backend and add the results as suggestions.
  const handleTableRegionExtract = useCallback(
    async (fieldName: string, _bbox: BoundingBoxData) => {
      if (!selectedDocId) return;
      setLoadingSuggestions(true);
      try {
        const result = await api.suggestField(selectedDocId, fieldName);
        const newSuggestions = result.suggestions || [];
        if (newSuggestions.length > 0) {
          setSuggestions((prev) => [...prev, ...newSuggestions]);
          toast.success(
            `Extracted ${newSuggestions.length} row${newSuggestions.length !== 1 ? "s" : ""} from table — review and approve below`,
          );
        } else {
          toast.info("No table data found for this field.");
        }
      } catch (error: any) {
        toast.error(`Table extraction failed: ${error.message}`);
      } finally {
        setLoadingSuggestions(false);
      }
    },
    [selectedDocId],
  );

  const handleAnnotationCreate = useCallback(
    (fieldName: string, value: any, data: TextSpanData | BoundingBoxData) => {
      const annotationType = "start" in data ? "text_span" : "bbox";

      // Check if this is an array field (contains dot notation like "field.property")
      const isArrayField = fieldName.includes(".");

      // Add instance_num to annotation_data if it's an array field
      const annotationData = isArrayField
        ? { ...data, instance_num: activeInstanceNum }
        : data;

      createAnnotationMutation.mutate({
        fieldName,
        value,
        annotationData,
        annotationType,
      });

      // Whole-table bbox drawn — auto-extract table contents from that region
      const isTableBbox =
        !isArrayField &&
        annotationType === "bbox" &&
        entityTypes.find((et) => et.name === fieldName && et.fieldKind === "table");
      if (isTableBbox) {
        handleTableRegionExtract(fieldName, data as BoundingBoxData);
        return;
      }

      if (!autoAdvanceRow || !isArrayField) {
        return;
      }

      const templateFields = effectiveTemplateFields.filter((field) =>
        field.includes("."),
      );

      if (templateFields.length === 0 || !templateFields.includes(fieldName)) {
        return;
      }

      const fieldsInRow = new Set(
        annotations
          .filter((annotation) => {
            const instanceNum = Number(
              (annotation.annotation_data as unknown as Record<string, unknown>)
                ?.instance_num,
            );
            return (
              Number.isFinite(instanceNum) && instanceNum === activeInstanceNum
            );
          })
          .map((annotation) => annotation.field_name),
      );
      fieldsInRow.add(fieldName);

      const completed = templateFields.every((field) => fieldsInRow.has(field));
      if (completed) {
        setActiveInstanceNum((prev) => Math.min(prev + 1, MAX_ROW_NUM));
      }
    },
    [
      activeInstanceNum,
      annotations,
      autoAdvanceRow,
      createAnnotationMutation,
      effectiveTemplateFields,
      entityTypes,
      handleTableRegionExtract,
    ],
  );

  // Handle annotation deletion
  const handleAnnotationDelete = useCallback(
    (annotationId: string) => {
      deleteAnnotationMutation.mutate(annotationId);
    },
    [deleteAnnotationMutation],
  );

  const handleAnnotationsDeleteBulk = useCallback(
    async (ids: string[]) => {
      await Promise.all(
        ids.map((id) => deleteAnnotationMutation.mutateAsync(id)),
      );
      refetchAnnotations();
    },
    [deleteAnnotationMutation, refetchAnnotations],
  );

  // Focus an annotation in the active document view (text/PDF/image)
  const focusAnnotationInDocument = useCallback(
    (annotation: GroundTruthAnnotation) => {
      const annotationType = annotation.annotation_type;
      if (annotationType === "bbox") {
        const bbox = annotation.annotation_data as BoundingBoxData;
        if (
          selectedDocument?.file_type?.toLowerCase() === "pdf" &&
          typeof bbox?.page === "number"
        ) {
          const pageEl = document.querySelector(
            `.react-pdf__Page[data-page-number="${bbox.page}"]`,
          ) as HTMLElement | null;
          if (pageEl) {
            pageEl.scrollIntoView({ behavior: "smooth", block: "center" });
          }
        }
      }

      const target = document.querySelector(
        `[data-annotation-id="${annotation.id}"]`,
      ) as HTMLElement | null;
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "center" });
        target.classList.add("dl-focus-outline");
        setTimeout(() => {
          target.classList.remove("dl-focus-outline");
        }, 1200);
        return;
      }

      // Text annotator keeps a stable helper for text-span cases.
      TextSpanAnnotator.scrollToAnnotation(annotation.id);
    },
    [selectedDocument],
  );

  // Clear suggestions when document changes
  useEffect(() => {
    setSuggestions([]);
  }, [selectedDocId]);

  // Close export menu on outside click or escape.
  useEffect(() => {
    if (!exportMenuVisible) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (!exportMenuRef.current?.contains(event.target as Node)) {
        setExportMenuVisible(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setExportMenuVisible(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [exportMenuVisible]);

  // AI suggest annotations
  const handleAISuggest = useCallback(async () => {
    if (!selectedDocId) return;
    setLoadingSuggestions(true);
    try {
      const result = await api.suggestAnnotations(selectedDocId);
      const existingFields = new Set(annotations.map((a) => a.field_name));
      const filtered = (result.suggestions || []).filter((s) => {
        const instanceNum = (s.annotation_data as any)?.instance_num;
        if (instanceNum) {
          return !annotations.some(
            (a) =>
              a.field_name === s.field_name &&
              (a.annotation_data as any)?.instance_num === instanceNum,
          );
        }
        return !existingFields.has(s.field_name);
      });
      setSuggestions(filtered);
      const skipped = (result.suggestions?.length || 0) - filtered.length;
      if (skipped > 0) {
        toast.success(
          `Generated ${filtered.length} suggestions (${skipped} already labeled)`,
        );
      } else {
        toast.success(
          `Generated ${filtered.length} suggestion${filtered.length !== 1 ? "s" : ""}`,
        );
      }
    } catch (error: any) {
      toast.error(`Failed to generate suggestions: ${error.message}`);
    } finally {
      setLoadingSuggestions(false);
    }
  }, [selectedDocId, annotations]);

  // Approve suggestion — saves as ground truth annotation
  const approveSuggestionMutation = useMutation({
    mutationFn: async (suggestion: AnnotationSuggestion) => {
      if (!selectedDocId) throw new Error("No document selected");
      return api.createGroundTruthAnnotation(selectedDocId, {
        document_id: selectedDocId,
        field_name: suggestion.field_name,
        value: suggestion.value, // Keep original type (string or array) - don't stringify
        annotation_type: suggestion.annotation_type,
        annotation_data: suggestion.annotation_data,
        labeled_by: "ai_approved",
      });
    },
    onSuccess: (_, suggestion) => {
      refetchAnnotations();
      setSuggestions((prev) => prev.filter((s) => s.id !== suggestion.id));
      toast.success("Suggestion approved");
    },
    onError: (error: Error) => {
      toast.error(`Failed to approve suggestion: ${error.message}`);
    },
  });

  const handleSuggestionApprove = useCallback(
    (suggestion: AnnotationSuggestion) => {
      approveSuggestionMutation.mutate(suggestion);
    },
    [approveSuggestionMutation],
  );

  const handleSuggestionReject = useCallback((id: string) => {
    setSuggestions((prev) => prev.filter((s) => s.id !== id));
  }, []);

  const handleAcceptAllSuggestions = useCallback(async () => {
    if (suggestions.length === 0) return;

    toast.promise(
      Promise.all(
        suggestions.map((s) => approveSuggestionMutation.mutateAsync(s)),
      ),
      {
        loading: `Accepting ${suggestions.length} suggestions...`,
        success: () => {
          setSuggestions([]);
          return `Accepted ${suggestions.length} suggestions`;
        },
        error: "Failed to accept some suggestions",
      },
    );
  }, [suggestions, approveSuggestionMutation]);

  const handleDeleteAllAnnotations = useCallback(async () => {
    if (annotations.length === 0) return;

    const confirmed = window.confirm(
      `Are you sure you want to delete all ${annotations.length} annotations? This cannot be undone.`,
    );

    if (!confirmed) return;

    toast.promise(
      Promise.all(
        annotations.map((a) => deleteAnnotationMutation.mutateAsync(a.id)),
      ),
      {
        loading: `Deleting ${annotations.length} annotations...`,
        success: `Deleted ${annotations.length} annotations`,
        error: "Failed to delete some annotations",
      },
    );
  }, [annotations, deleteAnnotationMutation]);

  // Global keyboard shortcuts
  useEffect(() => {
    const resetRowShortcut = () => {
      rowShortcutAwaitRef.current = false;
      rowShortcutDigitsRef.current = "";
      if (rowShortcutTimerRef.current !== null) {
        window.clearTimeout(rowShortcutTimerRef.current);
        rowShortcutTimerRef.current = null;
      }
    };

    const scheduleRowShortcutTimeout = () => {
      if (rowShortcutTimerRef.current !== null) {
        window.clearTimeout(rowShortcutTimerRef.current);
      }
      rowShortcutTimerRef.current = window.setTimeout(resetRowShortcut, 1200);
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }

      // Row prompt shortcut: R + number
      if (
        !e.ctrlKey &&
        !e.metaKey &&
        !e.altKey &&
        e.key.toLowerCase() === "r"
      ) {
        rowShortcutAwaitRef.current = true;
        rowShortcutDigitsRef.current = "";
        scheduleRowShortcutTimeout();
        e.preventDefault();
        return;
      }

      if (rowShortcutAwaitRef.current && /^[0-9]$/.test(e.key)) {
        rowShortcutDigitsRef.current += e.key;
        const parsed = parseInt(rowShortcutDigitsRef.current, 10);
        if (Number.isFinite(parsed) && parsed > 0) {
          setActiveInstanceNum(Math.min(parsed, MAX_ROW_NUM));
        }
        if (rowShortcutDigitsRef.current.length >= 2) {
          resetRowShortcut();
        } else {
          scheduleRowShortcutTimeout();
        }
        e.preventDefault();
        return;
      }

      if (rowShortcutAwaitRef.current && e.key !== "Shift") {
        resetRowShortcut();
      }

      // Tab / Shift+Tab cycles entity types
      if (e.key === "Tab" && entityTypes.length > 0) {
        e.preventDefault();
        const direction = e.shiftKey ? -1 : 1;
        const currentIndex = activeEntityTypeId
          ? entityTypes.findIndex((et) => et.id === activeEntityTypeId)
          : -1;
        const nextIndex =
          (((currentIndex + direction) % entityTypes.length) +
            entityTypes.length) %
          entityTypes.length;
        setActiveEntityTypeId(entityTypes[nextIndex]?.id || null);
        return;
      }

      // Ctrl/Cmd + Arrow Up: increment row number
      if ((e.ctrlKey || e.metaKey) && e.key === "ArrowUp") {
        e.preventDefault();
        setActiveInstanceNum((prev) => Math.min(prev + 1, MAX_ROW_NUM));
        return;
      }

      // Ctrl/Cmd + Arrow Down: decrement row number
      if ((e.ctrlKey || e.metaKey) && e.key === "ArrowDown") {
        e.preventDefault();
        setActiveInstanceNum((prev) => Math.max(prev - 1, 1));
        return;
      }

      // Undo annotation
      if (
        (e.ctrlKey || e.metaKey) &&
        !e.shiftKey &&
        e.key.toLowerCase() === "z"
      ) {
        const lastAnnotation = annotations[annotations.length - 1];
        if (lastAnnotation) {
          deleteAnnotationMutation.mutate(lastAnnotation.id);
          e.preventDefault();
        }
        return;
      }

      // Duplicate last row-based field into next row
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "d") {
        const rowBased = [...annotations]
          .reverse()
          .find((annotation) => annotation.field_name.includes("."));
        if (!rowBased) return;

        const originalData = rowBased.annotation_data as unknown as Record<
          string,
          unknown
        >;
        const originalRow = Number(originalData?.instance_num);
        const sourceRow = Number.isFinite(originalRow)
          ? originalRow
          : activeInstanceNum;
        const nextRow = Math.min(sourceRow + 1, MAX_ROW_NUM);
        const duplicatedData = {
          ...originalData,
          instance_num: nextRow,
        } as TextSpanData | BoundingBoxData;

        createAnnotationMutation.mutate({
          fieldName: rowBased.field_name,
          value: rowBased.value,
          annotationData: duplicatedData,
          annotationType: rowBased.annotation_type,
        });
        setActiveInstanceNum(nextRow);
        e.preventDefault();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      if (rowShortcutTimerRef.current !== null) {
        window.clearTimeout(rowShortcutTimerRef.current);
      }
    };
  }, [
    activeEntityTypeId,
    activeInstanceNum,
    annotations,
    createAnnotationMutation,
    deleteAnnotationMutation,
    entityTypes,
  ]);

  // Calculate stats
  const stats = useMemo(() => {
    const chars = annotations.reduce((sum, ann) => {
      const data = ann.annotation_data as TextSpanData;
      return sum + (data?.text?.length || 0);
    }, 0);
    const words = annotations.reduce((sum, ann) => {
      const data = ann.annotation_data as TextSpanData;
      return sum + (data?.text?.trim().split(/\s+/).length || 0);
    }, 0);

    return {
      documents: documents.length,
      chars,
      words,
      annotations: annotations.length,
      coverage: "—", // Would need total doc length
    };
  }, [documents, annotations]);

  // Get annotation counts per entity type
  const entityCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const ann of annotations) {
      counts[ann.field_name] = (counts[ann.field_name] || 0) + 1;
    }
    return counts;
  }, [annotations]);

  const documentAnnotationCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const ann of annotations) {
      counts[ann.document_id] = (counts[ann.document_id] || 0) + 1;
    }
    return counts;
  }, [annotations]);

  // Render document viewer based on file type
  const renderDocumentViewer = () => {
    if (!selectedDocument) {
      return (
        <div className="dl-text-display-container">
          <div className="dl-empty-state">
            <div className="dl-empty-state-icon">📄</div>
            <div className="dl-empty-state-text">No document selected</div>
            <div className="dl-empty-state-hint">
              Select a document from the sidebar to start labelling
            </div>
          </div>
        </div>
      );
    }

    const fileType = selectedDocument.file_type.toLowerCase();
    const documentUrl = api.getDocumentFileUrl(selectedDocument.id);

    // PDF - render PDF with selectable text layer
    if (fileType === "pdf") {
      return (
        <PdfTextAnnotator
          documentId={selectedDocument.id}
          pdfUrl={documentUrl}
          annotations={annotations}
          entityTypes={entityTypes}
          activeEntityTypeId={activeEntityTypeId}
          activeRowNumber={activeInstanceNum}
          showTableGrid={tableDetectionMode}
          forceFieldChooser={inlineFieldSwitcher}
          preferredFieldIds={effectiveTemplateFields}
          onAnnotationCreate={handleAnnotationCreate}
          onAnnotationDelete={handleAnnotationDelete}
          onAnnotationsDeleteBulk={handleAnnotationsDeleteBulk}
          onActiveEntityChange={setActiveEntityTypeId}
          suggestions={suggestions}
          onSuggestionApprove={handleSuggestionApprove}
          onSuggestionReject={handleSuggestionReject}
        />
      );
    }

    // Images - use bounding box annotation
    if (["png", "jpg", "jpeg", "gif", "webp"].includes(fileType)) {
      return (
        <ImageBboxAnnotator
          documentId={selectedDocument.id}
          imageUrl={documentUrl}
          annotations={annotations}
          entityTypes={entityTypes}
          activeEntityTypeId={activeEntityTypeId}
          onAnnotationCreate={handleAnnotationCreate}
          onAnnotationDelete={handleAnnotationDelete}
          onActiveEntityChange={setActiveEntityTypeId}
          suggestions={suggestions}
          onSuggestionApprove={handleSuggestionApprove}
          onSuggestionReject={handleSuggestionReject}
        />
      );
    }

    // Text files - direct text span annotation
    // For now, show empty state (would need to fetch content)
    return (
      <div className="dl-text-display-container">
        <div className="dl-empty-state">
          <div className="dl-empty-state-icon">📝</div>
          <div className="dl-empty-state-text">Text file annotation</div>
          <div className="dl-empty-state-hint">
            Text file support coming soon
          </div>
        </div>
      </div>
    );
  };

  // Export functions
  const exportAs = (format: string) => {
    setExportMenuVisible(false);

    const data = {
      entity_types: entityTypes.map((et) => ({
        name: et.name,
        color: et.color,
      })),
      document: selectedDocument?.filename || "unknown",
      annotations: annotations.map((ann) => {
        const data = ann.annotation_data as TextSpanData;
        return {
          text: ann.value,
          label: ann.field_name,
          start: data?.start,
          end: data?.end,
        };
      }),
    };

    let content = "";
    let filename = "annotations";
    let mime = "text/plain";

    if (format === "json") {
      content = JSON.stringify(data, null, 2);
      filename = "annotations.json";
      mime = "application/json";
    } else if (format === "jsonl") {
      content = annotations
        .map((ann) => {
          const data = ann.annotation_data as TextSpanData;
          return JSON.stringify({
            text: ann.value,
            label: ann.field_name,
            start: data?.start,
            end: data?.end,
          });
        })
        .join("\n");
      filename = "annotations.jsonl";
    } else if (format === "csv") {
      const rows = ["text,label,start,end"];
      for (const ann of annotations) {
        const data = ann.annotation_data as TextSpanData;
        rows.push(
          `"${(ann.value || "").replace(/"/g, '""')}","${ann.field_name}",${data?.start || ""},${data?.end || ""}`,
        );
      }
      content = rows.join("\n");
      filename = "annotations.csv";
      mime = "text/csv";
    }

    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const copyAnnotations = () => {
    const text = annotations
      .map((ann) => {
        return `${ann.field_name}: "${ann.value}"`;
      })
      .join("\n");

    navigator.clipboard.writeText(text).then(() => {
      toast.success("Copied to clipboard");
    });
  };

  return mounted ? (
    <div className="data-labeller-v2 flex h-full flex-col gap-2">
      <Card className="shrink-0 overflow-hidden border-primary/20 bg-[var(--surface-panel)]">
        <div
          className="px-4 py-2 text-white"
          style={{
            background:
              "linear-gradient(110deg, rgba(79, 2, 89, 0.9), rgba(56, 1, 64, 0.82))",
          }}
        >
          <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-1">
              <h3 className="text-lg font-semibold leading-tight text-white">
                Label source documents with schema-aligned entities
              </h3>
            </div>
            <div className="grid grid-cols-3 gap-2 sm:min-w-[300px]">
              <div className="rounded-lg border border-white/30 bg-white/10 px-3 py-1.5">
                <p className="text-[10px] uppercase tracking-wider text-white/80">
                  Docs
                </p>
                <p className="text-sm font-semibold">{stats.documents}</p>
              </div>
              <div className="rounded-lg border border-white/30 bg-white/10 px-3 py-1.5">
                <p className="text-[10px] uppercase tracking-wider text-white/80">
                  Annotations
                </p>
                <p className="text-sm font-semibold">{stats.annotations}</p>
              </div>
              <div className="rounded-lg border border-white/30 bg-white/10 px-3 py-1.5">
                <p className="text-[10px] uppercase tracking-wider text-white/80">
                  Suggestions
                </p>
                <p className="text-sm font-semibold">{suggestions.length}</p>
              </div>
            </div>
          </div>
        </div>
      </Card>

      <div
        className={cn(
          "grid flex-1 grid-cols-1 gap-4 min-h-0",
          sidebarVisible
            ? "xl:grid-cols-[280px_minmax(0,1fr)]"
            : "xl:grid-cols-1",
        )}
      >
        {sidebarVisible && (
          <div className="flex flex-col min-h-0 xl:pr-1">
            <Card className="flex flex-1 flex-col overflow-hidden border-[var(--border-strong)] min-h-0">
              <CardHeader className="space-y-1 border-b border-[var(--border-subtle)] py-2 px-3">
                <CardTitle className="text-sm">Annotation Sidebar</CardTitle>
              </CardHeader>
              <CardContent className="min-h-0 flex-1 overflow-y-auto pt-3 px-3 pb-3">
                <div className="space-y-3">
                  {/* Documents */}
                  <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-elevated)] p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <p className="text-sm font-medium">Documents</p>
                      <Badge variant="outline">{documents.length}</Badge>
                    </div>
                    {documents.length === 0 ? (
                      <div className="rounded-lg border border-dashed border-[var(--border-strong)] p-3 text-sm text-muted-foreground">
                        No documents in this project.
                      </div>
                    ) : (
                      <div className="dl-documents-list">
                        {documents.map((doc) => (
                          <button
                            key={doc.id}
                            type="button"
                            className={cn(
                              "dl-document-item",
                              selectedDocId === doc.id && "active",
                            )}
                            onClick={() => setSelectedDocId(doc.id)}
                          >
                            {doc.file_type === "pdf" ? (
                              <FileText size={14} />
                            ) : (
                              <Image size={14} />
                            )}
                            <span className="dl-document-item-name">
                              {doc.filename}
                            </span>
                            <span className="dl-document-item-meta">
                              {documentAnnotationCounts[doc.id] || 0} ann.
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Fields */}
                  <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-elevated)] p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <p className="text-sm font-medium">Fields</p>
                      <Badge variant="outline">{entityTypes.length}</Badge>
                    </div>
                    <div className="relative mb-2">
                      <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                      <Input
                        value={fieldFilter}
                        onChange={(event) =>
                          setFieldFilter(event.target.value)
                        }
                        placeholder="Filter fields..."
                        className="pl-8"
                      />
                    </div>
                    {entityTypes.length === 0 ? (
                      <div className="rounded-lg border border-dashed border-[var(--border-strong)] p-3 text-sm text-muted-foreground">
                        Select a classified document to load schema fields.
                      </div>
                    ) : (
                      <div className="dl-entity-types-list pr-1">
                        {Object.entries(filteredGroupedEntityTypes).map(
                          ([groupName, groupTypes]) => {
                            const isRoot = groupName === "_root";
                            const isExpanded =
                              isRoot || expandedGroups.has(groupName);
                            return (
                              <div
                                key={groupName}
                                className="dl-entity-group"
                              >
                                {!isRoot && (() => {
                                  const tableEt = entityTypes.find(
                                    (et) =>
                                      et.name === groupName &&
                                      et.fieldKind === "table",
                                  );
                                  const isTableActive =
                                    !!tableEt &&
                                    activeEntityTypeId === tableEt.id;
                                  const toggleGroup = () => {
                                    const next = new Set(expandedGroups);
                                    if (next.has(groupName)) {
                                      next.delete(groupName);
                                    } else {
                                      next.add(groupName);
                                    }
                                    setExpandedGroups(next);
                                  };
                                  return (
                                    <div className="dl-entity-group-header flex items-center gap-0.5">
                                      <button
                                        type="button"
                                        className="flex-shrink-0 p-1 rounded hover:bg-[var(--state-hover)]"
                                        onClick={toggleGroup}
                                        title={
                                          isExpanded
                                            ? "Collapse group"
                                            : "Expand group"
                                        }
                                      >
                                        <ChevronDown
                                          size={13}
                                          className={cn(
                                            "transition-transform text-[var(--text-secondary)]",
                                            !isExpanded && "-rotate-90",
                                          )}
                                        />
                                      </button>
                                      {tableEt ? (
                                        <button
                                          type="button"
                                          className={cn(
                                            "flex flex-1 items-center gap-1.5 rounded px-1.5 py-1 text-left text-xs font-medium transition-colors",
                                            isTableActive
                                              ? "bg-[var(--dl-accent-soft)]"
                                              : "hover:bg-[var(--state-hover)] text-[var(--text-secondary)]",
                                          )}
                                          style={
                                            isTableActive
                                              ? { color: tableEt.color }
                                              : undefined
                                          }
                                          onClick={() =>
                                            setActiveEntityTypeId(
                                              isTableActive ? null : tableEt.id,
                                            )
                                          }
                                          title="Select table field — then drag on the PDF to draw a bounding box"
                                        >
                                          <Table2
                                            size={12}
                                            style={
                                              isTableActive
                                                ? { color: tableEt.color }
                                                : undefined
                                            }
                                          />
                                          <span>{groupName}</span>
                                          <span
                                            className="ml-auto"
                                            style={{
                                              fontSize: "10px",
                                              opacity: 0.6,
                                            }}
                                          >
                                            {groupTypes.length}
                                          </span>
                                        </button>
                                      ) : (
                                        <button
                                          type="button"
                                          className="flex flex-1 items-center gap-1 text-left text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--state-hover)] rounded px-1 py-1"
                                          onClick={toggleGroup}
                                        >
                                          <span>{groupName}</span>
                                          <span className="dl-entity-group-count">
                                            {groupTypes.length}
                                          </span>
                                        </button>
                                      )}
                                    </div>
                                  );
                                })()}
                                {isExpanded &&
                                  groupTypes
                                    .filter((t) => t.fieldKind !== "table")
                                    .map((type) => {
                                    const fieldName = type.name;
                                    const displayName =
                                      getFieldLeafName(fieldName);
                                    const globalIndex =
                                      entityTypes.findIndex(
                                        (et) => et.id === type.id,
                                      );
                                    return (
                                      <button
                                        key={type.id}
                                        type="button"
                                        className={cn(
                                          "dl-entity-type-item",
                                          activeEntityTypeId === type.id &&
                                            "active",
                                        )}
                                        style={{
                                          ...(activeEntityTypeId === type.id
                                            ? { color: type.color }
                                            : undefined),
                                          paddingLeft: isRoot ? "8px" : "24px",
                                        }}
                                        onClick={() =>
                                          setActiveEntityTypeId(
                                            activeEntityTypeId === type.id
                                              ? null
                                              : type.id,
                                          )
                                        }
                                      >
                                        <div
                                          className="dl-entity-color-dot"
                                          style={{ background: type.color }}
                                        />
                                        <span className="dl-entity-type-name">
                                          {displayName}
                                        </span>
                                        {globalIndex < 9 && (
                                          <span className="dl-kbd">
                                            {globalIndex + 1}
                                          </span>
                                        )}
                                        <span className="dl-entity-type-count">
                                          {entityCounts[fieldName] || 0}
                                        </span>
                                      </button>
                                    );
                                  })}
                              </div>
                            );
                          },
                        )}
                      </div>
                    )}
                  </div>

                  {/* AI Suggestions */}
                  <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-elevated)] p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <p className="text-sm font-medium">Suggestions</p>
                      <div className="flex items-center gap-2">
                        {suggestions.length > 0 && (
                          <Badge variant="outline">{suggestions.length}</Badge>
                        )}
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="h-7 gap-1 px-2 text-xs"
                          onClick={handleAISuggest}
                          disabled={!selectedDocId || loadingSuggestions}
                          title="Generate AI annotation suggestions"
                        >
                          {loadingSuggestions ? (
                            <Loader2 size={12} className="animate-spin" />
                          ) : (
                            <Sparkles size={12} />
                          )}
                          Suggest
                        </Button>
                      </div>
                    </div>
                    {suggestions.length === 0 ? (
                      <p className="text-xs text-muted-foreground">
                        Run Suggest to generate model proposals for this
                        document.
                      </p>
                    ) : (
                      <div className="space-y-2">
                        <Button
                          type="button"
                          size="sm"
                          className="w-full h-7 text-xs"
                          onClick={handleAcceptAllSuggestions}
                          disabled={loadingSuggestions}
                        >
                          Accept All ({suggestions.length})
                        </Button>
                        {(() => {
                          // Group table-cell suggestions into a single card per table
                          const tableNames = new Set(
                            entityTypes
                              .filter((et) => et.fieldKind === "table")
                              .map((et) => et.name),
                          );
                          const tableGroupMap = new Map<string, typeof suggestions>();
                          const individualSugs: typeof suggestions = [];
                          for (const s of suggestions) {
                            const prefix = s.field_name.includes(".")
                              ? s.field_name.split(".")[0]
                              : null;
                            if (prefix && tableNames.has(prefix)) {
                              if (!tableGroupMap.has(prefix)) tableGroupMap.set(prefix, []);
                              tableGroupMap.get(prefix)!.push(s);
                            } else {
                              individualSugs.push(s);
                            }
                          }
                          return (
                            <>
                              {/* Table group cards — one per table field */}
                              {Array.from(tableGroupMap.entries()).map(([prefix, groupSugs]) => {
                                const rowCount = new Set(
                                  groupSugs.map(
                                    (s) =>
                                      (s.annotation_data as Record<string, unknown>)?.instance_num,
                                  ),
                                ).size;
                                const color =
                                  entityTypes.find((et) => et.name === prefix)?.color;
                                return (
                                  <div
                                    key={`table-group-${prefix}`}
                                    className="rounded-md border border-[var(--border-subtle)] bg-white p-2"
                                  >
                                    <div className="flex items-center justify-between gap-2">
                                      <span className="flex items-center gap-1.5 text-xs font-medium">
                                        <span
                                          className="inline-block h-2.5 w-2.5 rounded-full"
                                          style={{ background: color }}
                                        />
                                        {prefix}
                                      </span>
                                      <Badge variant="outline">
                                        {rowCount} row{rowCount !== 1 ? "s" : ""}
                                      </Badge>
                                    </div>
                                    <div className="mt-2 flex gap-2">
                                      <Button
                                        type="button"
                                        size="sm"
                                        className="h-7 flex-1 px-2 text-xs"
                                        onClick={() =>
                                          groupSugs.forEach((s) =>
                                            handleSuggestionApprove(s),
                                          )
                                        }
                                      >
                                        Accept all rows
                                      </Button>
                                      <Button
                                        type="button"
                                        size="sm"
                                        variant="outline"
                                        className="h-7 px-2 text-xs"
                                        onClick={() =>
                                          groupSugs.forEach((s) =>
                                            handleSuggestionReject(s.id),
                                          )
                                        }
                                      >
                                        Reject
                                      </Button>
                                    </div>
                                  </div>
                                );
                              })}
                              {/* Individual (non-table) suggestion cards */}
                              {individualSugs.map((suggestion) => (
                          <div
                            key={suggestion.id}
                            className="rounded-md border border-[var(--border-subtle)] bg-white p-2"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-xs font-medium">
                                {getFieldLeafName(suggestion.field_name)}
                              </span>
                              <Badge variant="outline">
                                {Math.round(
                                  (suggestion.confidence || 0) * 100,
                                )}
                                %
                              </Badge>
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {formatAnnotationValue(suggestion.value, 120)}
                            </p>
                            <div className="mt-2 flex gap-2">
                              <Button
                                type="button"
                                size="sm"
                                className="h-7 px-2 text-xs"
                                onClick={() =>
                                  handleSuggestionApprove(suggestion)
                                }
                              >
                                Accept
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-7 px-2 text-xs"
                                onClick={() =>
                                  handleSuggestionReject(suggestion.id)
                                }
                              >
                                Reject
                              </Button>
                            </div>
                          </div>
                        ))}
                            </>
                          );
                        })()}
                      </div>
                    )}
                  </div>

                  {/* Annotations */}
                  <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-elevated)] p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <p className="text-sm font-medium">Annotations</p>
                      <Badge variant="outline">{annotations.length}</Badge>
                    </div>
                    {annotations.length === 0 ? (
                      <div className="rounded-lg border border-dashed border-[var(--border-strong)] p-3 text-sm text-muted-foreground">
                        No annotations yet.
                      </div>
                    ) : (() => {
                      const tableNames = new Set(
                        entityTypes
                          .filter((et) => et.fieldKind === "table")
                          .map((et) => et.name),
                      );
                      // Group table annotations (cell-level dots + whole-table bbox)
                      const tableGroups = new Map<string, typeof annotations>();
                      const leafAnnotations: typeof annotations = [];
                      annotations.forEach((ann) => {
                        const prefix = ann.field_name.includes(".")
                          ? ann.field_name.split(".")[0]
                          : ann.field_name;
                        if (tableNames.has(prefix)) {
                          const grp = tableGroups.get(prefix) ?? [];
                          grp.push(ann);
                          tableGroups.set(prefix, grp);
                        } else {
                          leafAnnotations.push(ann);
                        }
                      });
                      return (
                        <div className="dl-annotations-list max-h-[240px] overflow-y-auto pr-1">
                          {Array.from(tableGroups.entries()).map(([tableName, grpAnns]) => {
                            const et = entityTypes.find((e) => e.name === tableName);
                            const color = et?.color || BEAZLEY_PALETTE.light;
                            const rowNums = new Set(
                              grpAnns
                                .map((a) => Number((a.annotation_data as any)?.instance_num))
                                .filter((n) => Number.isFinite(n) && n > 0),
                            );
                            const rowCount = rowNums.size || grpAnns.length;
                            return (
                              <div key={tableName} className="dl-annotation-item">
                                <span
                                  className="dl-annotation-label-chip"
                                  style={{ background: `${color}30`, color }}
                                >
                                  {tableName}
                                </span>
                                <span className="dl-annotation-text-preview">
                                  {rowCount} {rowCount === 1 ? "row" : "rows"}
                                </span>
                                <button
                                  type="button"
                                  className="dl-annotation-remove"
                                  onClick={() =>
                                    handleAnnotationsDeleteBulk(grpAnns.map((a) => a.id))
                                  }
                                  title="Remove all"
                                >
                                  ×
                                </button>
                              </div>
                            );
                          })}
                          {leafAnnotations.map((ann) => {
                            const entityType = entityTypes.find(
                              (entity) => entity.name === ann.field_name,
                            );
                            const color = entityType?.color || BEAZLEY_PALETTE.light;
                            const preview = formatAnnotationValue(ann.value, 40);
                            const instanceNum = Number(
                              (ann.annotation_data as unknown as Record<string, unknown>)?.instance_num,
                            );
                            return (
                              <div
                                key={ann.id}
                                className="dl-annotation-item"
                                onClick={() => focusAnnotationInDocument(ann)}
                              >
                                {Number.isFinite(instanceNum) && (
                                  <span className="dl-annotation-label-chip dl-annotation-chip-meta">
                                    {instanceNum}
                                  </span>
                                )}
                                <span
                                  className="dl-annotation-label-chip"
                                  style={{ background: `${color}30`, color }}
                                >
                                  {getFieldLeafName(ann.field_name)}
                                </span>
                                <span className="dl-annotation-text-preview">
                                  "{preview}"
                                </span>
                                <button
                                  type="button"
                                  className="dl-annotation-remove"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    handleAnnotationDelete(ann.id);
                                  }}
                                  title="Remove"
                                >
                                  ×
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      );
                    })()}
                  </div>

                  {/* Settings */}
                  <Collapsible className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-elevated)]">
                    <CollapsibleTrigger asChild>
                      <button
                        type="button"
                        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left hover:bg-[var(--state-hover)]"
                      >
                        <p className="text-sm font-medium">Settings</p>
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      </button>
                    </CollapsibleTrigger>
                    <CollapsibleContent className="space-y-4 border-t border-[var(--border-subtle)] px-3 pb-3 pt-3">
                      <div className="space-y-2">
                        <div className="flex items-center justify-between gap-3 text-xs">
                          <span>Inline field switcher on highlight</span>
                          <Switch
                            checked={inlineFieldSwitcher}
                            onCheckedChange={setInlineFieldSwitcher}
                          />
                        </div>
                        <div className="flex items-center justify-between gap-3 text-xs">
                          <span>Table detection grid overlay</span>
                          <Switch
                            checked={tableDetectionMode}
                            onCheckedChange={setTableDetectionMode}
                          />
                        </div>
                      </div>

                      <div>
                        <p className="text-xs font-medium mb-1.5">
                          Row Template Fields
                        </p>
                        {rowAwareFieldNames.length === 0 ? (
                          <p className="text-xs text-muted-foreground">
                            No row-based fields found in the active schema.
                          </p>
                        ) : (
                          <div className="space-y-1">
                            {activeGroupFieldNames.map((field) => {
                              const selected =
                                selectedTemplateFields.includes(field);
                              return (
                                <button
                                  key={field}
                                  type="button"
                                  onClick={() =>
                                    setSelectedTemplateFields((prev) =>
                                      prev.includes(field)
                                        ? prev.filter(
                                            (entry) => entry !== field,
                                          )
                                        : [...prev, field],
                                    )
                                  }
                                  className={cn(
                                    "flex w-full items-center justify-between rounded-md border px-2 py-1 text-xs",
                                    selected
                                      ? "border-[var(--interactive-accent)] bg-[var(--dl-accent-soft)]"
                                      : "border-[var(--border-subtle)] bg-white",
                                  )}
                                >
                                  <span>{getFieldLeafName(field)}</span>
                                  {selected ? (
                                    <Check size={13} />
                                  ) : (
                                    <X size={13} />
                                  )}
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </div>

                      <div>
                        <p className="text-xs font-medium mb-1.5">Export</p>
                        <div className="flex flex-wrap gap-2">
                          <div
                            className="dl-export-dropdown"
                            ref={exportMenuRef}
                          >
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() =>
                                setExportMenuVisible(!exportMenuVisible)
                              }
                            >
                              Export{" "}
                              <ChevronDown className="ml-1 h-3 w-3" />
                            </Button>
                            <div
                              className={`dl-export-menu ${exportMenuVisible ? "visible" : ""}`}
                            >
                              <button
                                type="button"
                                className="dl-export-menu-item"
                                onClick={() => exportAs("json")}
                              >
                                JSON
                              </button>
                              <button
                                type="button"
                                className="dl-export-menu-item"
                                onClick={() => exportAs("jsonl")}
                              >
                                JSONL
                              </button>
                              <button
                                type="button"
                                className="dl-export-menu-item"
                                onClick={() => exportAs("csv")}
                              >
                                CSV
                              </button>
                            </div>
                          </div>
                          <Button
                            type="button"
                            size="sm"
                            className="gap-1.5"
                            onClick={copyAnnotations}
                            disabled={annotations.length === 0}
                          >
                            <Copy className="h-3 w-3" />
                            Copy
                          </Button>
                        </div>
                      </div>
                    </CollapsibleContent>
                  </Collapsible>
                </div>

              </CardContent>
            </Card>
          </div>
        )}

        <div
          className={cn(
            "flex flex-col min-h-0",
            sidebarVisible &&
              "border-l border-[var(--border-subtle)] pl-0 xl:pl-4",
          )}
        >
          <Card className="flex flex-1 flex-col overflow-hidden min-h-0">
            <CardHeader className="space-y-2 border-b border-[var(--border-subtle)] py-2 px-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  {activeEntityType && (
                    <div className="flex items-center gap-1.5 text-sm">
                      <div
                        className="w-2 h-2 rounded-full"
                        style={{ background: activeEntityType.color }}
                      />
                      <span className="font-medium">
                        {activeEntityType.name}
                      </span>
                      {activeEntityType.name.includes(".") && (
                        <span className="text-xs text-muted-foreground">
                          Row {activeInstanceNum}
                        </span>
                      )}
                    </div>
                  )}
                  {selectedDocument && (
                    <Badge variant="outline" className="text-xs">
                      {selectedDocument.filename}
                    </Badge>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-1.5 justify-end">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={toggleSidebarVisibility}
                  >
                    {sidebarMode === "hidden" ? "Show Panel" : "Hide Panel"}
                  </Button>
                  {selectedDocId && annotations.length > 0 && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="gap-1 h-7 px-2 text-xs text-destructive hover:bg-destructive hover:text-destructive-foreground"
                      onClick={handleDeleteAllAnnotations}
                    >
                      <Trash2 size={12} />
                      Delete All
                    </Button>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent className="flex-1 min-h-0 overflow-auto p-0">
              <div className="h-full min-h-0">{renderDocumentViewer()}</div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  ) : null;
}
