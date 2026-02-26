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
  Sparkles,
  Trash2,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatAnnotationValue } from "@/lib/utils";
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

interface DataLabellerV2Props {}

export function DataLabellerV2({}: DataLabellerV2Props) {
  const projectId = localStorage.getItem("selected-project") || "all";
  const exportMenuRef = useRef<HTMLDivElement | null>(null);

  // Persist state in sessionStorage (survives tab switches, cleared when browser closes)
  const [selectedDocId, setSelectedDocId] = useState<string | null>(() => {
    try {
      return (
        sessionStorage.getItem(`labeller-selected-doc-${projectId}`) || null
      );
    } catch {
      return null;
    }
  });

  const [activeEntityTypeId, setActiveEntityTypeId] = useState<string | null>(
    () => {
      try {
        return (
          sessionStorage.getItem(`labeller-active-entity-${projectId}`) || null
        );
      } catch {
        return null;
      }
    },
  );

  const [activeInstanceNum, setActiveInstanceNum] = useState<number>(() => {
    try {
      const stored = sessionStorage.getItem(`labeller-active-row-${projectId}`);
      return stored ? parseInt(stored, 10) : 1;
    } catch {
      return 1;
    }
  });

  const [exportMenuVisible, setExportMenuVisible] = useState(false);
  const [localStorageVersion, setLocalStorageVersion] = useState(0);
  const [suggestions, setSuggestions] = useState<AnnotationSuggestion[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  // Fetch documents
  const { data: documentsData } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.listDocuments(),
  });

  // Filter documents by project
  const documents = useMemo(() => {
    if (!documentsData?.documents || !projectId || projectId === "all") {
      return [];
    }

    try {
      const stored = localStorage.getItem("uu-projects");
      if (!stored) return [];

      const projects = JSON.parse(stored);
      const project = projects.find((p: { id: string }) => p.id === projectId);
      if (!project) return [];

      const projectDocumentIds = project.documentIds || [];
      return documentsData.documents.filter((doc) =>
        projectDocumentIds.includes(doc.id),
      );
    } catch (error) {
      console.error("Error filtering documents:", error);
      return [];
    }
  }, [documentsData, projectId, localStorageVersion]);

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

  // Listen for localStorage changes
  useEffect(() => {
    const handleStorageChange = () => setLocalStorageVersion((v) => v + 1);
    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, []);

  // Get selected document
  const selectedDocument = documents.find((d) => d.id === selectedDocId);

  // Get schema fields from document type
  const schemaFields = selectedDocument?.document_type?.schema_fields || [];

  // Convert schema fields to entity types with colors
  const entityTypes: EntityType[] = useMemo(() => {
    const flattenFields = (fields: any[], prefix = ""): string[] => {
      const result: string[] = [];
      for (const field of fields) {
        const path = prefix ? `${prefix}.${field.name}` : field.name;

        if (
          field.type === "array" &&
          field.items?.type === "object" &&
          field.items.properties
        ) {
          // Array of objects - flatten nested properties
          for (const [propName, propField] of Object.entries(
            field.items.properties,
          )) {
            result.push(
              ...flattenFields(
                [{ ...(propField as object), name: propName }],
                path,
              ),
            );
          }
        } else if (field.type === "object" && field.properties) {
          // Object - flatten nested properties
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
          // Leaf field
          result.push(path);
        }
      }
      return result;
    };

    const fieldNames = flattenFields(schemaFields);
    return fieldNames.map((name, i) => ({
      id: name,
      name: name,
      color: ENTITY_COLORS[i % ENTITY_COLORS.length],
    }));
  }, [schemaFields]);

  // Group entity types by parent for hierarchical display
  const groupedEntityTypes = useMemo(() => {
    const groups: Record<string, EntityType[]> = {};

    entityTypes.forEach((et) => {
      const parts = et.name.split(".");
      if (parts.length > 1) {
        const parent = parts[0];
        if (!groups[parent]) {
          groups[parent] = [];
        }
        groups[parent].push(et);
      } else {
        // Top-level fields
        if (!groups["_root"]) {
          groups["_root"] = [];
        }
        groups["_root"].push(et);
      }
    });

    return groups;
  }, [entityTypes]);

  // Auto-expand all groups by default
  useEffect(() => {
    const allGroups = Object.keys(groupedEntityTypes).filter(
      (g) => g !== "_root",
    );
    setExpandedGroups(new Set(allGroups));
  }, [groupedEntityTypes]);

  // Keyboard shortcuts for row number control
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + Arrow Up: increment row number
      if ((e.ctrlKey || e.metaKey) && e.key === "ArrowUp") {
        e.preventDefault();
        setActiveInstanceNum((prev) => Math.min(prev + 1, 20));
      }
      // Ctrl/Cmd + Arrow Down: decrement row number
      if ((e.ctrlKey || e.metaKey) && e.key === "ArrowDown") {
        e.preventDefault();
        setActiveInstanceNum((prev) => Math.max(prev - 1, 1));
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

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
      value: string;
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
  const handleAnnotationCreate = useCallback(
    (
      fieldName: string,
      value: string,
      data: TextSpanData | BoundingBoxData,
    ) => {
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
    },
    [createAnnotationMutation, activeInstanceNum],
  );

  // Handle annotation deletion
  const handleAnnotationDelete = useCallback(
    (annotationId: string) => {
      deleteAnnotationMutation.mutate(annotationId);
    },
    [deleteAnnotationMutation],
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

  // Calculate stats
  const stats = useMemo(() => {
    const text = selectedDocument ? "" : ""; // We'd need document content for accurate stats
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
  }, [documents, annotations, selectedDocument]);

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

  // Get active entity type info
  const activeEntityType = entityTypes.find(
    (et) => et.id === activeEntityTypeId,
  );

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
          onAnnotationCreate={handleAnnotationCreate}
          onAnnotationDelete={handleAnnotationDelete}
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

  // Generate output summary as JSON
  const outputSummary = useMemo(() => {
    if (annotations.length === 0) {
      return "No annotations yet. Select an entity type from the sidebar, then highlight text in the document to label it.";
    }

    const jsonData = {
      document: selectedDocument?.filename || "unknown",
      annotations: annotations.map((ann) => {
        const data = ann.annotation_data as TextSpanData & BoundingBoxData;
        const entry: Record<string, unknown> = {
          field: ann.field_name,
          value: ann.value,
        };
        if (data?.start !== undefined) {
          entry.start = data.start;
          entry.end = data.end;
        }
        if (data?.page !== undefined) {
          entry.page = data.page;
        }
        return entry;
      }),
    };

    return JSON.stringify(jsonData, null, 2);
  }, [annotations, selectedDocument]);

  return (
    <div className="data-labeller-v2 flex h-full min-h-0 flex-col gap-6 overflow-auto xl:overflow-hidden">
      <Card className="overflow-hidden border-primary/20 bg-[var(--surface-panel)]">
        <div className="bg-gradient-to-r from-primary to-[var(--interactive-primary-hover)] px-6 py-6 text-primary-foreground">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-2">
              <p className="text-[11px] uppercase tracking-[0.18em] text-primary-foreground/80">
                annotation workspace
              </p>
              <h3 className="text-2xl font-semibold leading-tight text-primary-foreground">
                Label source documents with schema-aligned entities
              </h3>
              <p className="max-w-2xl text-sm text-primary-foreground/80">
                Select a document, activate an entity type, and highlight content
                to create ground truth labels for extraction quality workflows.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:min-w-[280px]">
              <div className="rounded-lg border border-white/30 bg-white/10 px-3 py-2">
                <p className="text-[11px] uppercase tracking-wider text-primary-foreground/80">
                  Documents
                </p>
                <p className="text-lg font-semibold">{stats.documents}</p>
              </div>
              <div className="rounded-lg border border-white/30 bg-white/10 px-3 py-2">
                <p className="text-[11px] uppercase tracking-wider text-primary-foreground/80">
                  Annotations
                </p>
                <p className="text-lg font-semibold">{stats.annotations}</p>
              </div>
              <div className="rounded-lg border border-white/30 bg-white/10 px-3 py-2">
                <p className="text-[11px] uppercase tracking-wider text-primary-foreground/80">
                  Words Tagged
                </p>
                <p className="text-lg font-semibold">{stats.words}</p>
              </div>
              <div className="rounded-lg border border-white/30 bg-white/10 px-3 py-2">
                <p className="text-[11px] uppercase tracking-wider text-primary-foreground/80">
                  Active Row
                </p>
                <p className="text-lg font-semibold">{activeInstanceNum}</p>
              </div>
            </div>
          </div>
        </div>
        <CardContent className="flex flex-wrap items-center gap-2 py-4">
          {selectedDocument ? (
            <Badge variant="outline">Document: {selectedDocument.filename}</Badge>
          ) : (
            <Badge variant="outline">No document selected</Badge>
          )}
          {activeEntityType ? (
            <Badge
              variant="outline"
              style={{
                borderColor: `${activeEntityType.color}66`,
                color: activeEntityType.color,
                backgroundColor: `${activeEntityType.color}18`,
              }}
            >
              Active Type: {activeEntityType.name}
            </Badge>
          ) : (
            <Badge variant="outline">No active entity type</Badge>
          )}
          <span className="text-xs text-muted-foreground">
            Keyboard: 1-9 select type, Esc deselect, Del removes last, Ctrl/Cmd +
            ↑/↓ changes row
          </span>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 xl:min-h-0 xl:flex-1 xl:grid-cols-[340px_minmax(0,1fr)]">
        <div className="space-y-4 xl:min-h-0 xl:overflow-auto xl:pr-1">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between gap-2">
                <div className="space-y-1">
                  <CardTitle className="text-base">Documents</CardTitle>
                  <CardDescription>
                    Select a document in this project to begin labelling.
                  </CardDescription>
                </div>
                <Badge variant="outline">{documents.length}</Badge>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
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
                      className={`dl-document-item ${selectedDocId === doc.id ? "active" : ""}`}
                      onClick={() => setSelectedDocId(doc.id)}
                    >
                      {doc.file_type === "pdf" ? (
                        <FileText size={14} />
                      ) : (
                        <Image size={14} />
                      )}
                      <span className="dl-document-item-name">{doc.filename}</span>
                      <span className="dl-document-item-meta">
                        {documentAnnotationCounts[doc.id] || 0} ann.
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <div className="space-y-1">
                <CardTitle className="text-base">Table Row Number</CardTitle>
                <CardDescription>
                  Choose the row index used when annotating array fields.
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="dl-row-grid">
                {Array.from({ length: 10 }, (_, idx) => idx + 1).map((num) => (
                  <button
                    key={num}
                    type="button"
                    onClick={() => setActiveInstanceNum(num)}
                    className={`dl-row-chip ${activeInstanceNum === num ? "active" : ""}`}
                  >
                    {num}
                  </button>
                ))}
              </div>
              <div className="dl-row-current">
                Current row: <strong>{activeInstanceNum}</strong>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between gap-2">
                <div className="space-y-1">
                  <CardTitle className="text-base">Entity Types</CardTitle>
                  <CardDescription>
                    Click an entity type to annotate directly with highlight
                    selection.
                  </CardDescription>
                </div>
                <Badge variant="outline">{entityTypes.length}</Badge>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              {entityTypes.length === 0 ? (
                <div className="rounded-lg border border-dashed border-[var(--border-strong)] p-3 text-sm text-muted-foreground">
                  Select a classified document to load schema fields.
                </div>
              ) : (
                <div className="dl-entity-types-list max-h-[320px] overflow-y-auto pr-1">
                  {Object.entries(groupedEntityTypes).map(
                    ([groupName, groupTypes]) => {
                      const isExpanded = expandedGroups.has(groupName);
                      const isRoot = groupName === "_root";

                      return (
                        <div key={groupName} className="dl-entity-group">
                          {!isRoot && (
                            <button
                              type="button"
                              className="dl-entity-group-header w-full text-left"
                              onClick={() => {
                                const newExpanded = new Set(expandedGroups);
                                if (isExpanded) {
                                  newExpanded.delete(groupName);
                                } else {
                                  newExpanded.add(groupName);
                                }
                                setExpandedGroups(newExpanded);
                              }}
                            >
                              <ChevronDown
                                size={14}
                                className={
                                  isExpanded
                                    ? "transition-transform"
                                    : "-rotate-90 transition-transform"
                                }
                              />
                              <span>{groupName}</span>
                              <span className="dl-entity-group-count">
                                {groupTypes.length}
                              </span>
                            </button>
                          )}
                          {(isRoot || isExpanded) &&
                            groupTypes.map((et) => {
                              const globalIndex = entityTypes.findIndex(
                                (e) => e.id === et.id,
                              );
                              const displayName =
                                et.name.split(".").pop() || et.name;

                              return (
                                <button
                                  type="button"
                                  key={et.id}
                                  className={`dl-entity-type-item ${activeEntityTypeId === et.id ? "active" : ""}`}
                                  style={{
                                    ...(activeEntityTypeId === et.id
                                      ? { color: et.color }
                                      : undefined),
                                    paddingLeft: isRoot ? "8px" : "24px",
                                  }}
                                  onClick={() =>
                                    setActiveEntityTypeId(
                                      activeEntityTypeId === et.id
                                        ? null
                                        : et.id,
                                    )
                                  }
                                >
                                  <div
                                    className="dl-entity-color-dot"
                                    style={{ background: et.color }}
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
                                    {entityCounts[et.name] || 0}
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
              <div className="dl-shortcut-hint">
                <span className="dl-kbd">1</span>-<span className="dl-kbd">9</span>{" "}
                activate type, <span className="dl-kbd">Esc</span> deselect,{" "}
                <span className="dl-kbd">Del</span> remove last
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between gap-2">
                <div className="space-y-1">
                  <CardTitle className="text-base">Annotations</CardTitle>
                  <CardDescription>
                    Review labels and click any row to focus it in the document.
                  </CardDescription>
                </div>
                <Badge variant="outline">{annotations.length}</Badge>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              {annotations.length === 0 ? (
                <div className="rounded-lg border border-dashed border-[var(--border-strong)] p-3 text-sm text-muted-foreground">
                  No annotations yet.
                </div>
              ) : (
                <div className="dl-annotations-list max-h-[320px] overflow-y-auto pr-1">
                  {annotations.map((ann) => {
                    const et = entityTypes.find((e) => e.name === ann.field_name);
                    const color = et?.color || BEAZLEY_PALETTE.light;
                    const preview = formatAnnotationValue(ann.value, 30);
                    const instanceNum = (ann.annotation_data as any)?.instance_num;

                    return (
                      <div
                        key={ann.id}
                        className="dl-annotation-item"
                        onClick={() => focusAnnotationInDocument(ann)}
                      >
                        {instanceNum && (
                          <span className="dl-annotation-label-chip dl-annotation-chip-meta">
                            {instanceNum}
                          </span>
                        )}
                        <span
                          className="dl-annotation-label-chip"
                          style={{ background: `${color}30`, color }}
                        >
                          {ann.field_name.split(".").pop()}
                        </span>
                        <span className="dl-annotation-text-preview">
                          "{preview}
                          {(ann.value?.length || 0) > 30 ? "..." : ""}"
                        </span>
                        <button
                          type="button"
                          className="dl-annotation-remove"
                          onClick={(e) => {
                            e.stopPropagation();
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
              )}
            </CardContent>
          </Card>
        </div>

        <div className="min-h-0 space-y-4 xl:flex xl:flex-col xl:overflow-hidden">
          <Card className="flex min-h-[620px] flex-col overflow-hidden xl:min-h-0 xl:flex-1">
            <CardHeader className="space-y-3 border-b border-[var(--border-subtle)]">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 space-y-1">
                  <CardTitle className="text-base">Labelling Workspace</CardTitle>
                  <CardDescription>
                    {activeEntityType ? (
                      <span>
                        Labelling as <strong>{activeEntityType.name}</strong>
                        {selectedDocument && (
                          <>
                            {" "}
                            in <strong>{selectedDocument.filename}</strong>
                          </>
                        )}
                        . Highlight text or draw a box to create an annotation.
                      </span>
                    ) : entityTypes.length === 0 ? (
                      <span>Select a classified document to load schema fields.</span>
                    ) : (
                      <span>
                        Select an entity type, then highlight text to label it.
                      </span>
                    )}
                  </CardDescription>
                </div>
                {selectedDocument && (
                  <Badge variant="outline" className="max-w-full">
                    {selectedDocument.filename}
                  </Badge>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="gap-1.5"
                  onClick={handleAISuggest}
                  disabled={!selectedDocId || loadingSuggestions}
                  title="Generate AI annotation suggestions"
                >
                  {loadingSuggestions ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : (
                    <Sparkles size={13} />
                  )}
                  Suggest
                  {suggestions.length > 0 && (
                    <span className="dl-annotation-label-chip dl-annotation-chip-meta">
                      {suggestions.length}
                    </span>
                  )}
                </Button>

                {suggestions.length > 0 && (
                  <Button
                    type="button"
                    size="sm"
                    className="gap-1.5"
                    onClick={handleAcceptAllSuggestions}
                    disabled={!selectedDocId || loadingSuggestions}
                    title={`Accept all ${suggestions.length} suggestions`}
                  >
                    <Sparkles size={13} />
                    Accept All ({suggestions.length})
                  </Button>
                )}

                {selectedDocId && annotations.length > 0 && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="gap-1.5 text-destructive hover:bg-destructive hover:text-destructive-foreground"
                    onClick={handleDeleteAllAnnotations}
                    title={`Delete all ${annotations.length} annotations`}
                  >
                    <Trash2 size={13} />
                    Delete All ({annotations.length})
                  </Button>
                )}

                {activeEntityType && (
                  <div className="dl-active-label-indicator">
                    <div
                      className="dl-active-label-dot"
                      style={{ background: activeEntityType.color }}
                    />
                    <span>{activeEntityType.name}</span>
                    {activeEntityType.name.includes(".") && (
                      <span className="dl-row-pill">Row {activeInstanceNum}</span>
                    )}
                  </div>
                )}
              </div>

              <div className="dl-stats-bar rounded-lg border border-[var(--border-subtle)]">
                <div>
                  Documents: <strong>{stats.documents}</strong>
                </div>
                <div>
                  Annotations: <strong>{stats.annotations}</strong>
                </div>
                <div>
                  Words annotated: <strong>{stats.words}</strong>
                </div>
              </div>
            </CardHeader>
            <CardContent className="flex-1 min-h-0 overflow-hidden p-0">
              <div className="h-full min-h-[420px] xl:min-h-0">
                {renderDocumentViewer()}
              </div>
            </CardContent>
          </Card>

          <Card className="overflow-hidden xl:shrink-0">
            <CardHeader className="border-b border-[var(--border-subtle)] py-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="space-y-1">
                  <CardTitle className="text-sm">Output</CardTitle>
                  <CardDescription>
                    Structured annotation payload for downstream evaluation and
                    export.
                  </CardDescription>
                </div>
                <div className="flex flex-wrap gap-2">
                  <div className="dl-export-dropdown" ref={exportMenuRef}>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setExportMenuVisible(!exportMenuVisible)}
                    >
                      Export <ChevronDown className="ml-1 h-3 w-3" />
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
            </CardHeader>
            <CardContent className="p-0">
              <pre
                className={`dl-output-content ${annotations.length > 0 ? "has-content" : ""}`}
              >
                {outputSummary}
              </pre>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
