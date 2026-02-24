/**
 * DataLabeller - Main component for creating ground truth annotations
 */

import { useState, useEffect, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type GroundTruthAnnotation, type AnnotationSuggestion } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Loader2, Sparkles, ThumbsUp, ThumbsDown, AlertCircle, AlertTriangle } from "lucide-react";
import { TextAnnotator } from "@/components/labeller/TextAnnotator";
import { PdfBboxAnnotator } from "@/components/labeller/PdfBboxAnnotator";
import { ImageAnnotator } from "@/components/labeller/ImageAnnotator";
import { toast } from "sonner";
import { formatAnnotationValue } from "@/lib/utils";

export function DataLabeller() {
  const queryClient = useQueryClient();
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<AnnotationSuggestion[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [localStorageVersion, setLocalStorageVersion] = useState(0);

  // Get project filter from localStorage
  const projectId = localStorage.getItem("selected-project") || "all";

  // Fetch documents
  const { data: documentsData } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.listDocuments(),
  });

  // Filter documents by project (exact same logic as DocumentPool - NO FALLBACKS)
  const documents = useMemo(() => {
    console.log('[DataLabeller] Filtering documents:', {
      totalDocs: documentsData?.documents?.length || 0,
      projectId,
      localStorageVersion
    });
    
    if (!documentsData?.documents) {
      console.log('[DataLabeller] No documents data');
      return [];
    }
    
    // If no projectId, show NOTHING - fail explicitly
    if (!projectId || projectId === "all") {
      console.log('[DataLabeller] No project selected or "all" selected - showing nothing');
      return [];
    }
    
    // Get document IDs for this specific project from localStorage
    let projectDocumentIds: string[] = [];
    try {
      const stored = localStorage.getItem("uu-projects");
      if (!stored) {
        console.log('[DataLabeller] No uu-projects in localStorage');
        return [];
      }
      
      const projects = JSON.parse(stored);
      console.log('[DataLabeller] Found projects in localStorage:', projects.length);
      
      const project = projects.find((p: { id: string }) => p.id === projectId);
      
      if (!project) {
        console.log('[DataLabeller] Project not found in localStorage:', projectId);
        return [];
      }
      
      projectDocumentIds = project.documentIds || [];
      console.log('[DataLabeller] Project document IDs:', projectDocumentIds);
    } catch (error) {
      console.error("[DataLabeller] Error reading uu-projects from localStorage:", error);
      return [];
    }
    
    // Filter to only documents that belong to this project
    const filtered = documentsData.documents.filter(doc => projectDocumentIds.includes(doc.id));
    console.log('[DataLabeller] Filtered documents:', filtered.length);
    return filtered;
  }, [documentsData, projectId, localStorageVersion]);

  // Sync localStorage document IDs with actual documents from API (same as DocumentPool)
  // This removes stale IDs that no longer exist in the database
  useEffect(() => {
    if (!documentsData || !projectId || projectId === "all") return;
    
    try {
      const stored = localStorage.getItem("uu-projects");
      if (!stored) return;
      
      const projects = JSON.parse(stored);
      const projectIndex = projects.findIndex((p: { id: string }) => p.id === projectId);
      if (projectIndex < 0) return;
      
      const storedDocIds: string[] = projects[projectIndex].documentIds || [];
      if (storedDocIds.length === 0) return;
      
      // Get all document IDs that actually exist in the API
      const existingDocIds = new Set(documentsData.documents.map(doc => doc.id));
      
      // Filter to only IDs that exist in the API
      const validDocIds = storedDocIds.filter(id => existingDocIds.has(id));
      
      // Only update if there are stale IDs to remove
      if (validDocIds.length < storedDocIds.length) {
        console.log(`[DataLabeller] Syncing localStorage: removed ${storedDocIds.length - validDocIds.length} stale document IDs`);
        projects[projectIndex].documentIds = validDocIds;
        projects[projectIndex].docCount = validDocIds.length;
        localStorage.setItem("uu-projects", JSON.stringify(projects));
        setLocalStorageVersion(v => v + 1);
      }
    } catch (err) {
      console.error("[DataLabeller] Failed to sync localStorage document IDs:", err);
    }
  }, [documentsData, projectId]);

  // Get selected document
  const selectedDocument = documents.find(d => d.id === selectedDocId);

  // Fetch document type for selected document
  const { data: documentTypesData } = useQuery({
    queryKey: ["document-types"],
    queryFn: () => api.listDocumentTypes(),
  });

  const selectedDocType = selectedDocument?.document_type;
  const schemaFields = selectedDocType?.schema_fields || [];

  // Flatten schema fields to include nested properties
  // For array of objects, create entries like "line_items.quantity", "line_items.line_total", etc.
  const flattenedFields = useMemo(() => {
    const flattened: Array<{ path: string; label: string; parentType?: string }> = [];
    
    schemaFields.forEach(field => {
      if (field.type === "array" && field.items?.type === "object" && field.items.properties) {
        // Array of objects - add each property as a separate labelable field
        Object.entries(field.items.properties).forEach(([propName, propField]: [string, any]) => {
          flattened.push({
            path: `${field.name}.${propName}`,
            label: `${field.name} → ${propName}`,
            parentType: "array"
          });
        });
      } else if (field.type === "object" && field.properties) {
        // Object - add each property as a separate labelable field
        Object.entries(field.properties).forEach(([propName, propField]: [string, any]) => {
          flattened.push({
            path: `${field.name}.${propName}`,
            label: `${field.name} → ${propName}`,
            parentType: "object"
          });
        });
      } else {
        // Simple field
        flattened.push({
          path: field.name,
          label: field.name
        });
      }
    });
    
    return flattened;
  }, [schemaFields]);

  // Fetch annotations for selected document
  const { data: annotationsData, refetch: refetchAnnotations } = useQuery({
    queryKey: ["annotations", selectedDocId],
    queryFn: () => selectedDocId ? api.getGroundTruthAnnotations(selectedDocId) : Promise.resolve({ annotations: [], total: 0 }),
    enabled: !!selectedDocId,
  });

  const annotations = annotationsData?.annotations || [];

  // Refresh document list when tab becomes active (catches updates from Documents tab)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        console.log('[DataLabeller] Tab became visible, refreshing document list');
        setLocalStorageVersion(v => v + 1);
        queryClient.invalidateQueries({ queryKey: ["documents"] });
      }
    };
    
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [queryClient]);

  // Also refresh when the component mounts or projectId changes
  useEffect(() => {
    console.log('[DataLabeller] Component mounted or project changed, refreshing');
    setLocalStorageVersion(v => v + 1);
    queryClient.invalidateQueries({ queryKey: ["documents"] });
  }, [projectId, queryClient]);

  // Create annotation mutation
  const createAnnotationMutation = useMutation({
    mutationFn: (data: { fieldName: string; value: string; annotationData: any }) =>
      api.createGroundTruthAnnotation(selectedDocId!, {
        document_id: selectedDocId!,
        field_name: data.fieldName,
        value: data.value,
        annotation_type: selectedDocument?.file_type === "pdf" ? "bbox" : "text_span",
        annotation_data: data.annotationData,
        labeled_by: "manual",
      }),
    onSuccess: () => {
      refetchAnnotations();
      toast.success("Annotation created");
    },
    onError: (error: any) => {
      toast.error(`Failed to create annotation: ${error.message}`);
    },
  });

  // Delete annotation mutation
  const deleteAnnotationMutation = useMutation({
    mutationFn: (annotationId: string) => api.deleteGroundTruthAnnotation(annotationId),
    onSuccess: () => {
      refetchAnnotations();
      toast.success("Annotation deleted");
    },
    onError: (error: any) => {
      toast.error(`Failed to delete annotation: ${error.message}`);
    },
  });

  // AI Suggestions
  const handleAISuggest = async () => {
    if (!selectedDocId) return;

    setLoadingSuggestions(true);
    try {
      const result = await api.suggestAnnotations(selectedDocId);
      setSuggestions(result.suggestions);
      toast.success(`Generated ${result.suggestions.length} suggestions`);
    } catch (error: any) {
      toast.error(`Failed to generate suggestions: ${error.message}`);
    } finally {
      setLoadingSuggestions(false);
    }
  };

  // Approve suggestion
  const approveSuggestionMutation = useMutation({
    mutationFn: ({ suggestionId, editedValue }: { suggestionId: string; editedValue?: any }) =>
      api.approveAnnotation(suggestionId, editedValue),
    onSuccess: () => {
      refetchAnnotations();
      setSuggestions(prev => prev.filter(s => s.id !== suggestionId));
      toast.success("Suggestion approved");
    },
    onError: (error: any) => {
      toast.error(`Failed to approve: ${error.message}`);
    },
  });

  // Reject suggestion
  const rejectSuggestionMutation = useMutation({
    mutationFn: (suggestionId: string) => api.rejectAnnotation(suggestionId),
    onSuccess: () => {
      setSuggestions(prev => prev.filter(s => s.id !== suggestionId));
      toast.success("Suggestion rejected");
    },
    onError: (error: any) => {
      toast.error(`Failed to reject: ${error.message}`);
    },
  });

  // Auto-select first document
  useEffect(() => {
    if (!selectedDocId && documents.length > 0) {
      setSelectedDocId(documents[0].id);
    }
  }, [documents, selectedDocId]);

  // Render document viewer based on file type
  const renderDocumentViewer = () => {
    if (!selectedDocument) {
      return (
        <Card className="flex items-center justify-center h-full">
          <CardContent className="text-center text-muted-foreground">
            <p>Select a document to start labeling</p>
          </CardContent>
        </Card>
      );
    }

    const fileType = selectedDocument.file_type.toLowerCase();
    // Get document URL (original file, no OCR needed)
    const documentUrl = api.getDocumentFileUrl(selectedDocument.id);

    if (fileType === "pdf") {
      return (
        <PdfBboxAnnotator
          documentId={selectedDocument.id}
          pdfUrl={documentUrl}
          annotations={annotations}
          selectedField={selectedField}
          onAnnotationCreate={(fieldName, value, annotationData) =>
            createAnnotationMutation.mutate({ fieldName, value, annotationData })
          }
          onAnnotationDelete={(annotationId) => deleteAnnotationMutation.mutate(annotationId)}
        />
      );
    } else if (["txt", "docx", "doc"].includes(fileType)) {
      return (
        <TextAnnotator
          content={selectedDocument.content || ""}
          annotations={annotations}
          selectedField={selectedField}
          onAnnotationCreate={(fieldName, value, annotationData) =>
            createAnnotationMutation.mutate({ fieldName, value, annotationData })
          }
          onAnnotationDelete={(annotationId) => deleteAnnotationMutation.mutate(annotationId)}
        />
      );
    } else if (["png", "jpg", "jpeg", "gif", "webp"].includes(fileType)) {
      return (
        <ImageAnnotator
          imageUrl={documentUrl}
          annotations={annotations}
          selectedField={selectedField}
          onAnnotationCreate={(fieldName, value, annotationData) =>
            createAnnotationMutation.mutate({ fieldName, value, annotationData })
          }
          onAnnotationDelete={(annotationId) => deleteAnnotationMutation.mutate(annotationId)}
        />
      );
    }

    return (
      <Card className="flex items-center justify-center h-full">
        <CardContent className="text-center text-muted-foreground">
          <p>Unsupported file type: {fileType}</p>
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="flex h-full gap-4">
      {/* Left Sidebar - Document & Field Selection */}
      <div className="w-80 flex-shrink-0 space-y-4 overflow-y-auto">
        {/* Document Selector */}
        <Card>
          <CardHeader>
            <CardTitle>Document</CardTitle>
            <CardDescription>Select a document to label</CardDescription>
          </CardHeader>
          <CardContent>
            {documents.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <p className="font-medium">No documents in this project</p>
                <p className="text-sm mt-2">Upload documents in the Documents tab first</p>
              </div>
            ) : (
              <Select value={selectedDocId || ""} onValueChange={setSelectedDocId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select document" />
                </SelectTrigger>
                <SelectContent>
                  {documents.map(doc => (
                    <SelectItem key={doc.id} value={doc.id}>
                      {doc.filename}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            {selectedDocument && (
              <div className="mt-4 space-y-2">
                <div className="text-sm">
                  <span className="text-muted-foreground">Type:</span>{" "}
                  <Badge variant="outline">{selectedDocument.file_type}</Badge>
                </div>
                {selectedDocType && (
                  <div className="text-sm">
                    <span className="text-muted-foreground">Schema:</span>{" "}
                    <Badge>{selectedDocType.name}</Badge>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Field Selector */}
        {flattenedFields.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Fields</CardTitle>
              <CardDescription>Select a field to annotate</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {flattenedFields.map(field => {
                const fieldAnnotations = annotations.filter(a => a.field_name === field.path);
                const isSelected = selectedField === field.path;

                return (
                  <Button
                    key={field.path}
                    variant={isSelected ? "default" : "outline"}
                    className="w-full justify-between text-left"
                    onClick={() => setSelectedField(isSelected ? null : field.path)}
                  >
                    <span className="truncate">{field.label}</span>
                    {fieldAnnotations.length > 0 && (
                      <Badge variant="secondary">{fieldAnnotations.length}</Badge>
                    )}
                  </Button>
                );
              })}
            </CardContent>
          </Card>
        )}

        {/* AI Suggestions */}
        {selectedDocId && selectedDocType && (
          <Card>
            <CardHeader>
              <CardTitle>AI Assistance</CardTitle>
              <CardDescription>Get AI-powered annotation suggestions</CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                className="w-full"
                onClick={handleAISuggest}
                disabled={loadingSuggestions}
              >
                {loadingSuggestions ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Sparkles className="mr-2 h-4 w-4" />
                    Suggest Annotations
                  </>
                )}
              </Button>

              {suggestions.length > 0 && (
                <div className="mt-4 space-y-2">
                  <p className="text-sm font-medium">{suggestions.length} Suggestions</p>
                  {suggestions.map(suggestion => (
                    <div key={suggestion.id} className="p-2 border rounded-lg space-y-2">
                      <div className="text-sm">
                        <span className="font-medium">{suggestion.field_name}:</span>{" "}
                        {formatAnnotationValue(suggestion.value, 50)}
                      </div>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => approveSuggestionMutation.mutate({ suggestionId: suggestion.id })}
                        >
                          <ThumbsUp className="h-3 w-3" />
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => rejectSuggestionMutation.mutate(suggestion.id)}
                        >
                          <ThumbsDown className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      {/* Right Panel - Document Viewer */}
      <div className="flex-1 min-w-0">
        {renderDocumentViewer()}
      </div>
    </div>
  );
}
