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
    <div className="data-labeller-v2 flex h-full overflow-hidden">
      {/* Sidebar */}
      <div className="dl-sidebar dl-contrast-panel">
        <div className="dl-sidebar-header">
          <FileText size={16} />
          Data Labelling Tool
        </div>

        {/* Documents section */}
        <div className="dl-sidebar-section">
          <div className="dl-section-title">
            Documents
            <span className="dl-meta-note">{documents.length}</span>
          </div>
          <div className="dl-section-content">
            {documents.length === 0 ? (
              <div className="dl-empty-note">No documents in this project</div>
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
          </div>
        </div>

        {/* Row Number Selector for Array Fields */}
        <div className="dl-sidebar-section">
          <div className="dl-section-title">
            Table Row Number
            <span className="dl-meta-note">for array fields</span>
          </div>
          <div className="dl-section-content">
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
          </div>
        </div>

        {/* Entity Types section */}
        <div className="dl-sidebar-section">
          <div className="dl-section-title">
            Entity Types
            <span className="dl-meta-note">click to activate</span>
          </div>
          <div className="dl-section-content">
            {entityTypes.length === 0 ? (
              <div className="dl-empty-note">
                Select a classified document to see schema fields
              </div>
            ) : (
              <div className="dl-entity-types-list">
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
                                    activeEntityTypeId === et.id ? null : et.id,
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
          </div>
          <div className="dl-shortcut-hint">
            <span className="dl-kbd">1</span>-<span className="dl-kbd">9</span>{" "}
            activate type · <span className="dl-kbd">Esc</span> deselect ·{" "}
            <span className="dl-kbd">Del</span> remove last ·{" "}
            <span className="dl-kbd">Ctrl</span>+
            <span className="dl-kbd">↑</span>/<span className="dl-kbd">↓</span>{" "}
            row
          </div>
        </div>

        {/* Annotations section */}
        <div className="dl-sidebar-section flex-grow">
          <div className="dl-section-title">
            Annotations
            <span className="dl-meta-note">{annotations.length}</span>
          </div>
          <div className="dl-section-content flex-1 overflow-y-auto">
            {annotations.length === 0 ? (
              <div className="dl-empty-note">No annotations yet</div>
            ) : (
              <div className="dl-annotations-list">
                {annotations.map((ann) => {
                  const et = entityTypes.find((e) => e.name === ann.field_name);
                  const color = et?.color || BEAZLEY_PALETTE.light;
                  const preview = formatAnnotationValue(ann.value, 30);
                  const instanceNum = (ann.annotation_data as any)
                    ?.instance_num;

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
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="dl-toolbar">
          <div className="dl-toolbar-info">
            {activeEntityType ? (
              <span>
                Labelling as <strong>{activeEntityType.name}</strong>
                {selectedDocument && (
                  <>
                    {" "}
                    in <strong>{selectedDocument.filename}</strong>
                  </>
                )}{" "}
                — highlight text to annotate
              </span>
            ) : entityTypes.length === 0 ? (
              <span>Select a classified document to see schema fields</span>
            ) : (
              <span>
                Select an entity type, then highlight text to label it
              </span>
            )}
          </div>
          {selectedDocId && (
            <button
              type="button"
              className="dl-btn dl-btn-sm dl-btn-icon"
              onClick={handleAISuggest}
              disabled={loadingSuggestions}
              title="Generate AI annotation suggestions"
            >
              {loadingSuggestions ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <Sparkles size={12} />
              )}
              Suggest
              {suggestions.length > 0 && (
                <span className="dl-annotation-label-chip dl-annotation-chip-meta">
                  {suggestions.length}
                </span>
              )}
            </button>
          )}
          {selectedDocId && suggestions.length > 0 && (
            <button
              type="button"
              className="dl-btn dl-btn-sm dl-btn-primary dl-btn-icon"
              onClick={handleAcceptAllSuggestions}
              disabled={loadingSuggestions}
              title={`Accept all ${suggestions.length} suggestions`}
            >
              <Sparkles size={12} />
              Accept All ({suggestions.length})
            </button>
          )}
          {selectedDocId && annotations.length > 0 && (
            <button
              type="button"
              className="dl-btn dl-btn-sm dl-btn-danger dl-btn-icon"
              onClick={handleDeleteAllAnnotations}
              title={`Delete all ${annotations.length} annotations`}
            >
              <Trash2 size={12} />
              Delete All ({annotations.length})
            </button>
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

        {/* Stats bar */}
        <div className="dl-stats-bar">
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

        {/* Document viewer */}
        <div className="flex-1 min-h-0 overflow-hidden">
          {renderDocumentViewer()}
        </div>

        {/* Output panel */}
        <div className="dl-output-panel">
          <div className="dl-output-header">
            <span className="dl-output-label">Output</span>
            <div className="dl-output-buttons">
              <div className="dl-export-dropdown" ref={exportMenuRef}>
                <button
                  type="button"
                  className="dl-btn dl-btn-sm"
                  onClick={() => setExportMenuVisible(!exportMenuVisible)}
                >
                  Export <ChevronDown className="ml-1 h-3 w-3" />
                </button>
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
              <button
                type="button"
                className="dl-btn dl-btn-sm dl-btn-primary"
                onClick={copyAnnotations}
              >
                <Copy className="mr-1 h-3 w-3" />
                Copy
              </button>
            </div>
          </div>
          <div
            className={`dl-output-content ${annotations.length > 0 ? "has-content" : ""}`}
          >
            {outputSummary}
          </div>
        </div>
      </div>
    </div>
  );
}
