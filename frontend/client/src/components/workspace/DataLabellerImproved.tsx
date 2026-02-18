/**
 * DataLabeller - Improved UI inspired by Label Studio
 * Features:
 * - Color-coded field labels
 * - Clear visual connection between annotations and fields
 * - Better annotation management
 * - Cleaner layout
 */

import { useState, useEffect, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type GroundTruthAnnotation, type AnnotationSuggestion } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Loader2, Sparkles, ThumbsUp, ThumbsDown, Trash2, Eye, EyeOff, Plus, ChevronDown, ChevronRight } from "lucide-react";
import { PdfBboxAnnotator } from "@/components/labeller/PdfBboxAnnotator";
import { ImageAnnotator } from "@/components/labeller/ImageAnnotator";
import { TextAnnotator } from "@/components/labeller/TextAnnotator";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

// Field colors for visual distinction
const FIELD_COLORS = [
  { bg: "bg-yellow-100", border: "border-yellow-400", text: "text-yellow-900", hex: "#fef08a" },
  { bg: "bg-green-100", border: "border-green-400", text: "text-green-900", hex: "#bbf7d0" },
  { bg: "bg-blue-100", border: "border-blue-400", text: "text-blue-900", hex: "#bfdbfe" },
  { bg: "bg-purple-100", border: "border-purple-400", text: "text-purple-900", hex: "#e9d5ff" },
  { bg: "bg-pink-100", border: "border-pink-400", text: "text-pink-900", hex: "#fbcfe8" },
  { bg: "bg-orange-100", border: "border-orange-400", text: "text-orange-900", hex: "#fed7aa" },
  { bg: "bg-cyan-100", border: "border-cyan-400", text: "text-cyan-900", hex: "#a5f3fc" },
  { bg: "bg-red-100", border: "border-red-400", text: "text-red-900", hex: "#fecaca" },
];

export function DataLabellerImproved() {
  const queryClient = useQueryClient();
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<AnnotationSuggestion[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [localStorageVersion, setLocalStorageVersion] = useState(0);
  const [hiddenFields, setHiddenFields] = useState<Set<string>>(new Set());
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [currentInstance, setCurrentInstance] = useState<Record<string, number>>({});

  const projectId = localStorage.getItem("selected-project") || "all";

  const { data: documentsData } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.listDocuments(),
  });

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
      return documentsData.documents.filter(doc => projectDocumentIds.includes(doc.id));
    } catch (error) {
      console.error("Error filtering documents:", error);
      return [];
    }
  }, [documentsData, projectId, localStorageVersion]);

  useEffect(() => {
    const handleStorageChange = () => setLocalStorageVersion(v => v + 1);
    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, []);

  const selectedDocument = documents.find(d => d.id === selectedDocId);

  const { data: documentTypesData } = useQuery({
    queryKey: ["document-types"],
    queryFn: () => api.listDocumentTypes(),
  });

  const selectedDocType = selectedDocument?.document_type;
  const schemaFields = selectedDocType?.schema_fields || [];

  // Group fields by parent for better organization
  const fieldGroups = useMemo(() => {
    const groups: Array<{
      parentName: string;
      parentType?: string;
      isGroup: boolean;
      colorIndex: number;
      children?: Array<{ path: string; label: string; colorIndex: number }>;
      path?: string;
      label?: string;
    }> = [];
    let colorIndex = 0;
    
    schemaFields.forEach(field => {
      if (field.type === "array" && field.items?.type === "object" && field.items.properties) {
        // Array of objects - create a group
        const children: Array<{ path: string; label: string; colorIndex: number }> = [];
        Object.entries(field.items.properties).forEach(([propName, propField]: [string, any]) => {
          children.push({
            path: `${field.name}.${propName}`,
            label: propName,
            colorIndex: colorIndex
          });
        });
        groups.push({
          parentName: field.name,
          parentType: "array",
          isGroup: true,
          colorIndex: colorIndex,
          children
        });
        colorIndex++;
      } else if (field.type === "object" && field.properties) {
        // Object - create a group
        const children: Array<{ path: string; label: string; colorIndex: number }> = [];
        Object.entries(field.properties).forEach(([propName, propField]: [string, any]) => {
          children.push({
            path: `${field.name}.${propName}`,
            label: propName,
            colorIndex: colorIndex
          });
        });
        groups.push({
          parentName: field.name,
          parentType: "object",
          isGroup: true,
          colorIndex: colorIndex,
          children
        });
        colorIndex++;
      } else {
        // Simple field
        groups.push({
          parentName: field.name,
          isGroup: false,
          colorIndex: colorIndex,
          path: field.name,
          label: field.name
        });
        colorIndex++;
      }
    });
    
    return groups;
  }, [schemaFields]);

  const { data: annotationsData, refetch: refetchAnnotations } = useQuery({
    queryKey: ["annotations", selectedDocId],
    queryFn: () => selectedDocId ? api.getGroundTruthAnnotations(selectedDocId) : Promise.resolve({ annotations: [], total: 0 }),
    enabled: !!selectedDocId,
  });

  const annotations = annotationsData?.annotations || [];

  const createAnnotationMutation = useMutation({
    mutationFn: async (data: { fieldName: string; value: string; annotationData: any }) => {
      if (!selectedDocId) throw new Error("No document selected");
      
      // Get parent field name (e.g., "line_items" from "line_items.quantity")
      const parentField = data.fieldName.split('.')[0];
      const instanceNum = currentInstance[parentField] || 1;
      
      // Add instance_num to annotation data if this is part of a group
      const isGroupedField = data.fieldName.includes('.');
      const annotationData = isGroupedField 
        ? { ...data.annotationData, instance_num: instanceNum }
        : data.annotationData;
      
      return api.createGroundTruthAnnotation(selectedDocId, {
        document_id: selectedDocId,
        field_name: data.fieldName,
        value: data.value,
        annotation_type: "bbox",
        annotation_data: annotationData,
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

  const handleAISuggest = async () => {
    if (!selectedDocId || !selectedDocType) return;
    
    setLoadingSuggestions(true);
    try {
      const result = await api.suggestAnnotations(selectedDocId);
      
      // Filter out suggestions for fields that already have annotations
      const existingFieldNames = new Set(annotations.map(a => a.field_name));
      const filteredSuggestions = (result.suggestions || []).filter(s => {
        // For array fields, check if this specific instance is already labeled
        const instanceNum = s.annotation_data?.instance_num;
        if (instanceNum) {
          // Check if this field + instance combo exists
          return !annotations.some(a => 
            a.field_name === s.field_name && 
            a.annotation_data?.instance_num === instanceNum
          );
        }
        // For simple fields, check if field exists at all
        return !existingFieldNames.has(s.field_name);
      });
      
      setSuggestions(filteredSuggestions);
      
      const skipped = (result.suggestions?.length || 0) - filteredSuggestions.length;
      if (skipped > 0) {
        toast.success(`Generated ${filteredSuggestions.length} suggestions (${skipped} already labeled)`);
      } else {
        toast.success(`Generated ${filteredSuggestions.length} suggestions`);
      }
    } catch (error: any) {
      toast.error(`Failed to generate suggestions: ${error.message}`);
    } finally {
      setLoadingSuggestions(false);
    }
  };

  const approveSuggestionMutation = useMutation({
    mutationFn: async ({ suggestionId, suggestion }: { suggestionId: string; suggestion: AnnotationSuggestion }) => {
      if (!selectedDocId) throw new Error("No document selected");
      // Create ground truth annotation from suggestion
      return api.createGroundTruthAnnotation(selectedDocId, {
        document_id: selectedDocId,
        field_name: suggestion.field_name,
        value: String(suggestion.value),
        annotation_type: "bbox",
        annotation_data: suggestion.annotation_data,
        labeled_by: "ai_approved",
      });
    },
    onSuccess: (_, variables) => {
      refetchAnnotations();
      setSuggestions(prev => prev.filter(s => s.id !== variables.suggestionId));
      toast.success("Suggestion approved and saved");
    },
    onError: (error: Error) => {
      toast.error(`Failed to approve: ${error.message}`);
    },
  });

  const rejectSuggestionMutation = useMutation({
    mutationFn: async (suggestionId: string) => {
      // Just remove from local state - suggestions are temporary
      return { suggestionId };
    },
    onSuccess: (_, suggestionId) => {
      setSuggestions(prev => prev.filter(s => s.id !== suggestionId));
      toast.success("Suggestion rejected");
    },
  });

  const getFieldColor = (fieldPath: string) => {
    const field = flattenedFields.find(f => f.path === fieldPath);
    return field ? FIELD_COLORS[field.colorIndex] : FIELD_COLORS[0];
  };

  const toggleFieldVisibility = (fieldPath: string) => {
    setHiddenFields(prev => {
      const next = new Set(prev);
      if (next.has(fieldPath)) {
        next.delete(fieldPath);
      } else {
        next.add(fieldPath);
      }
      return next;
    });
  };

  const groupedAnnotations = useMemo(() => {
    const groups: Record<string, GroundTruthAnnotation[]> = {};
    annotations.forEach(ann => {
      if (!groups[ann.field_name]) {
        groups[ann.field_name] = [];
      }
      groups[ann.field_name].push(ann);
    });
    return groups;
  }, [annotations]);

  // Group annotations by instance for array fields
  // Instance number is determined by the suffix in the label: e.g., "line_items_quantity_1" -> instance 1
  const instancedAnnotations = useMemo(() => {
    const result: Record<string, Array<{ instanceId: string; instanceNum: number; annotations: Record<string, GroundTruthAnnotation[]> }>> = {};
    
    fieldGroups.forEach(group => {
      if (group.isGroup && group.children) {
        const parentName = group.parentName;
        const instanceMap: Record<number, Record<string, GroundTruthAnnotation[]>> = {};
        
        // Get all annotations for this group's children
        group.children.forEach(child => {
          const childAnnotations = groupedAnnotations[child.path] || [];
          childAnnotations.forEach((ann, idx) => {
            // Extract instance number from annotation_data.instance_num, or use index + 1
            const instanceNum = ann.annotation_data?.instance_num || (idx + 1);
            
            if (!instanceMap[instanceNum]) {
              instanceMap[instanceNum] = {};
            }
            if (!instanceMap[instanceNum][child.path]) {
              instanceMap[instanceNum][child.path] = [];
            }
            instanceMap[instanceNum][child.path].push(ann);
          });
        });
        
        // Convert to sorted array
        const instances = Object.entries(instanceMap)
          .map(([num, annotations]) => ({
            instanceId: `${parentName}_${num}`,
            instanceNum: parseInt(num),
            annotations
          }))
          .sort((a, b) => a.instanceNum - b.instanceNum);
        
        result[parentName] = instances;
      }
    });
    
    return result;
  }, [annotations, fieldGroups, groupedAnnotations]);

  const renderDocumentViewer = () => {
    if (!selectedDocument) return null;

    const fileType = selectedDocument.file_type.toLowerCase();
    const documentUrl = api.getDocumentFileUrl(selectedDocument.id);

    if (fileType === "pdf") {
      return (
        <PdfBboxAnnotator
          documentId={selectedDocument.id}
          pdfUrl={documentUrl}
          annotations={annotations.filter(a => !hiddenFields.has(a.field_name))}
          suggestions={suggestions}
          selectedField={selectedField}
          onAnnotationCreate={(fieldName, value, annotationData) =>
            createAnnotationMutation.mutate({ fieldName, value, annotationData })
          }
          onAnnotationDelete={(annotationId) => deleteAnnotationMutation.mutate(annotationId)}
          onSuggestionApprove={(suggestion) => 
            approveSuggestionMutation.mutate({ suggestionId: suggestion.id, suggestion })
          }
          onSuggestionReject={(suggestionId) => rejectSuggestionMutation.mutate(suggestionId)}
        />
      );
    } else if (["png", "jpg", "jpeg", "gif", "webp"].includes(fileType)) {
      return (
        <ImageAnnotator
          imageUrl={documentUrl}
          annotations={annotations.filter(a => !hiddenFields.has(a.field_name))}
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
      {/* Left Sidebar */}
      <div className="w-80 flex-shrink-0 space-y-4 overflow-y-auto">
        {/* Document Selector */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Document</CardTitle>
          </CardHeader>
          <CardContent>
            {documents.length === 0 ? (
              <div className="text-center py-4 text-sm text-muted-foreground">
                <p>No documents in this project</p>
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

            {selectedDocument && selectedDocType && (
              <div className="mt-3 p-2 bg-muted rounded-md">
                <div className="text-xs text-muted-foreground">Schema</div>
                <div className="font-medium text-sm">{selectedDocType.name}</div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Fields & Labels */}
        {fieldGroups.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Labels</CardTitle>
              <CardDescription className="text-xs">
                Click to select, draw boxes on document
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-1">
              {fieldGroups.map(group => {
                const color = FIELD_COLORS[group.colorIndex];
                
                if (!group.isGroup) {
                  // Simple field
                  const fieldAnnotations = groupedAnnotations[group.path!] || [];
                  const isSelected = selectedField === group.path;
                  const isHidden = hiddenFields.has(group.path!);

                  return (
                    <div
                      key={group.path}
                      className={cn(
                        "group flex items-center gap-2 p-2 rounded-md border-2 transition-all cursor-pointer",
                        isSelected ? `${color.bg} ${color.border}` : "border-transparent hover:bg-muted",
                        isHidden && "opacity-50"
                      )}
                    >
                      <div
                        className="flex-1 flex items-center gap-2"
                        onClick={() => setSelectedField(isSelected ? null : group.path!)}
                      >
                        <div 
                          className={cn("w-3 h-3 rounded", color.bg, color.border, "border-2")}
                        />
                        <span className={cn("text-sm font-medium flex-1", isSelected && color.text)}>
                          {group.label}
                        </span>
                        {fieldAnnotations.length > 0 && (
                          <Badge variant="secondary" className="text-xs">
                            {fieldAnnotations.length}
                          </Badge>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleFieldVisibility(group.path!);
                        }}
                      >
                        {isHidden ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                      </Button>
                    </div>
                  );
                }

                // Group (array/object with children)
                const isExpanded = expandedGroups.has(group.parentName);
                const activeInstanceNum = currentInstance[group.parentName] || 0;
                const existingInstances = instancedAnnotations[group.parentName] || [];
                const totalAnnotations = group.children?.reduce((sum, child) => 
                  sum + (groupedAnnotations[child.path]?.length || 0), 0) || 0;
                
                // Count annotations for active instance
                const activeInstanceAnnotations = activeInstanceNum 
                  ? annotations.filter(ann => 
                      ann.annotation_data?.instance_num === activeInstanceNum &&
                      ann.field_name.startsWith(group.parentName + '.')
                    )
                  : [];

                return (
                  <div key={group.parentName} className="space-y-1">
                    {/* Group Header */}
                    <div className={cn("flex items-center gap-2 p-2 rounded-md border-2", color.bg, color.border)}>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-5 w-5 p-0"
                        onClick={() => {
                          setExpandedGroups(prev => {
                            const next = new Set(prev);
                            if (next.has(group.parentName)) {
                              next.delete(group.parentName);
                            } else {
                              next.add(group.parentName);
                            }
                            return next;
                          });
                        }}
                      >
                        {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                      </Button>
                      <div 
                        className={cn("w-3 h-3 rounded", color.bg, color.border, "border-2")}
                      />
                      <span className={cn("text-sm font-medium flex-1", color.text)}>
                        {group.parentName}
                      </span>
                      {totalAnnotations > 0 && (
                        <Badge variant="secondary" className="text-xs">
                          {totalAnnotations}
                        </Badge>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs"
                        onClick={() => {
                          // Get current instance number for this group
                          const currentNum = currentInstance[group.parentName];
                          
                          if (currentNum && group.children) {
                            // Check how many properties have been labeled for current instance
                            const activeInstanceAnnotations = annotations.filter(ann => 
                              ann.annotation_data?.instance_num === currentNum &&
                              ann.field_name.startsWith(group.parentName + '.')
                            );
                            
                            // If active instance has 0 annotations, don't allow adding new
                            if (activeInstanceAnnotations.length === 0) {
                              toast.error(`Label at least one field before adding a new instance`);
                              return;
                            }
                          }
                          
                          // Get existing instance count from annotations
                          const existingInstances = instancedAnnotations[group.parentName] || [];
                          const maxInstanceNum = existingInstances.reduce((max, inst) => Math.max(max, inst.instanceNum), 0);
                          const nextInstanceNum = maxInstanceNum + 1;
                          
                          setCurrentInstance(prev => ({ ...prev, [group.parentName]: nextInstanceNum }));
                          setExpandedGroups(prev => new Set(prev).add(group.parentName));
                          
                          // Auto-select first child field
                          if (group.children && group.children.length > 0) {
                            setSelectedField(group.children[0].path);
                          }
                          toast.success(`Started labeling ${group.parentName} #${nextInstanceNum}`);
                        }}
                      >
                        <Plus className="h-3 w-3 mr-1" />
                        Add
                      </Button>
                    </div>

                    {/* Children Fields */}
                    {isExpanded && group.children && (
                      <div className="ml-6 space-y-1">
                        {activeInstanceNum > 0 && (
                          <div className="text-xs text-muted-foreground px-2 py-1 flex items-center justify-between">
                            <span>Instance #{activeInstanceNum}</span>
                            <span className="text-xs">
                              {activeInstanceAnnotations.length}/{group.children.length} labeled
                            </span>
                          </div>
                        )}
                        {activeInstanceNum === 0 && existingInstances.length > 0 && (
                          <div className="text-xs text-muted-foreground px-2 py-1">
                            Click "Add" to start new instance
                          </div>
                        )}
                        {group.children.map(child => {
                          const fieldAnnotations = groupedAnnotations[child.path] || [];
                          const isSelected = selectedField === child.path;
                          const isHidden = hiddenFields.has(child.path);

                          return (
                            <div
                              key={child.path}
                              className={cn(
                                "group flex items-center gap-2 p-2 rounded-md border-2 transition-all cursor-pointer",
                                isSelected ? `${color.bg} ${color.border}` : "border-transparent hover:bg-muted",
                                isHidden && "opacity-50"
                              )}
                            >
                              <div
                                className="flex-1 flex items-center gap-2"
                                onClick={() => setSelectedField(isSelected ? null : child.path)}
                              >
                                <div 
                                  className={cn("w-2 h-2 rounded", color.bg, color.border, "border-2")}
                                />
                                <span className={cn("text-sm flex-1", isSelected && color.text)}>
                                  {child.label}
                                </span>
                                {fieldAnnotations.length > 0 && (
                                  <Badge variant="secondary" className="text-xs">
                                    {fieldAnnotations.length}
                                  </Badge>
                                )}
                              </div>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-5 w-5 p-0 opacity-0 group-hover:opacity-100"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  toggleFieldVisibility(child.path);
                                }}
                              >
                                {isHidden ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                              </Button>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </CardContent>
          </Card>
        )}

        {/* AI Suggestions */}
        {selectedDocId && selectedDocType && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">AI Assistance</CardTitle>
            </CardHeader>
            <CardContent>
              <Button
                className="w-full"
                size="sm"
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
                <div className="mt-3 space-y-2">
                  <div className="text-xs text-muted-foreground">{suggestions.length} suggestions</div>
                  {suggestions.slice(0, 3).map(suggestion => (
                    <div key={suggestion.id} className="p-2 border rounded-md space-y-2 text-xs">
                      <div>
                        <span className="font-medium">{suggestion.field_name}:</span>{" "}
                        {String(suggestion.value).substring(0, 30)}...
                      </div>
                      <div className="flex gap-1">
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-6 flex-1"
                          onClick={() => approveSuggestionMutation.mutate({ suggestionId: suggestion.id, suggestion })}
                        >
                          <ThumbsUp className="h-3 w-3" />
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-6 flex-1"
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

      {/* Center - Document Viewer */}
      <div className="flex-1 min-w-0">
        {renderDocumentViewer()}
      </div>

      {/* Right Sidebar - Annotations */}
      {selectedDocId && annotations.length > 0 && (
        <div className="w-80 flex-shrink-0 overflow-y-auto">
          <Card className="h-full">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Annotations ({annotations.length})</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {fieldGroups.map(group => {
                const color = FIELD_COLORS[group.colorIndex];
                
                if (!group.isGroup) {
                  // Simple field
                  const fieldAnnotations = groupedAnnotations[group.path!] || [];
                  if (fieldAnnotations.length === 0) return null;

                  return (
                    <div key={group.path} className="space-y-2">
                      <div className="flex items-center gap-2">
                        <div className={cn("w-3 h-3 rounded", color.bg, color.border, "border-2")} />
                        <span className="text-sm font-medium">{group.label}</span>
                        <Badge variant="secondary" className="text-xs">{fieldAnnotations.length}</Badge>
                      </div>
                      <div className="space-y-1 pl-5">
                        {fieldAnnotations.map(ann => (
                          <div
                            key={ann.id}
                            className={cn(
                              "group flex items-start gap-2 p-2 rounded border text-xs",
                              color.bg,
                              color.border
                            )}
                          >
                            <div className="flex-1 break-words">
                              {ann.value || <span className="text-muted-foreground italic">No value</span>}
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-5 w-5 p-0 opacity-0 group-hover:opacity-100"
                              onClick={() => deleteAnnotationMutation.mutate(ann.id)}
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </div>
                        ))}
                      </div>
                      <Separator />
                    </div>
                  );
                }

                // Group annotations by instance
                const instances = instancedAnnotations[group.parentName] || [];
                if (instances.length === 0) return null;

                return (
                  <div key={group.parentName} className="space-y-2">
                    <div className="flex items-center gap-2">
                      <div className={cn("w-3 h-3 rounded", color.bg, color.border, "border-2")} />
                      <span className="text-sm font-medium">{group.parentName}</span>
                      <Badge variant="secondary" className="text-xs">{instances.length} instances</Badge>
                    </div>
                    
                    {/* Show each instance as a card */}
                    <div className="space-y-2 pl-5">
                      {instances.map((instance) => (
                        <div 
                          key={instance.instanceId}
                          className={cn(
                            "p-3 rounded-lg border-2 space-y-2",
                            color.bg,
                            color.border
                          )}
                        >
                          <div className="text-xs font-semibold text-muted-foreground">
                            Instance #{instance.instanceNum}
                          </div>
                          
                          {group.children?.map(child => {
                            const fieldAnnotations = instance.annotations[child.path] || [];
                            if (fieldAnnotations.length === 0) return null;

                            return (
                              <div key={child.path} className="space-y-1">
                                <div className="text-xs font-medium opacity-70">{child.label}</div>
                                {fieldAnnotations.map(ann => (
                                  <div
                                    key={ann.id}
                                    className="group flex items-start gap-2 p-2 rounded bg-white/50 text-xs"
                                  >
                                    <div className="flex-1 break-words font-medium">
                                      {ann.value || <span className="text-muted-foreground italic">No value</span>}
                                    </div>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="h-4 w-4 p-0 opacity-0 group-hover:opacity-100"
                                      onClick={() => deleteAnnotationMutation.mutate(ann.id)}
                                    >
                                      <Trash2 className="h-3 w-3" />
                                    </Button>
                                  </div>
                                ))}
                              </div>
                            );
                          })}
                        </div>
                      ))}
                    </div>
                    <Separator />
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
