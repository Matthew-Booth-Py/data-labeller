import { useState, useRef, useMemo } from "react";
import { useQuery, useMutation, useQueryClient, useQueries } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { 
  Filter, 
  Search, 
  Grid, 
  List, 
  MoreVertical, 
  FileText, 
  Calendar, 
  CheckCircle, 
  AlertTriangle,
  Upload,
  RefreshCw,
  Trash2,
  Loader2,
  Wand2,
  Check,
  X,
  Sparkles,
  Edit2,
  Tags,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/hooks/use-toast";
import { api, DocumentSummary } from "@/lib/api";
import { format, parseISO } from "date-fns";

interface DocumentPoolProps {
  onDocumentClick?: (id: string) => void;
  projectId?: string;  // Track documents per project
}

export function DocumentPool({ onDocumentClick, projectId }: DocumentPoolProps) {
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('list');
  const [searchQuery, setSearchQuery] = useState("");
  const [localStorageVersion, setLocalStorageVersion] = useState(0);
  const [classifying, setClassifying] = useState(false);
  const [classifyingDocs, setClassifyingDocs] = useState<Set<string>>(new Set());
  const [suggestingLabels, setSuggestingLabels] = useState(false);
  const [suggestingLabelDocs, setSuggestingLabelDocs] = useState<Set<string>>(new Set());
  const [editingDoc, setEditingDoc] = useState<string | null>(null);
  const [classifications, setClassifications] = useState<Map<string, {
    type: string;
    typeId: string;
    confidence: number;
    reasoning: string;
    status: 'pending' | 'accepted' | 'rejected';
  }>>(new Map());
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Fetch documents from API
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.listDocuments(),
    staleTime: 0, // Always refetch when invalidated to show latest classification
  });

  // Fetch document types for manual classification
  const { data: documentTypesData } = useQuery({
    queryKey: ["documentTypes"],
    queryFn: () => api.listDocumentTypes(),
  });

  const documentTypes = Array.isArray(documentTypesData?.types) ? documentTypesData.types : [];

  // Get project's document IDs and filter - use useMemo to ensure recalculation
  const filteredData = useMemo(() => {
    if (!data) return data;
    
    // If no projectId, show nothing (documents must belong to a project)
    if (!projectId) {
      return { ...data, documents: [], total: 0 };
    }
    
    // Get document IDs for this specific project from localStorage
    let projectDocumentIds: string[] = [];
    try {
      const stored = localStorage.getItem("uu-projects");
      if (stored) {
        const projects = JSON.parse(stored);
        const project = projects.find((p: { id: string }) => p.id === projectId);
        projectDocumentIds = project?.documentIds || [];
      }
    } catch {
      projectDocumentIds = [];
    }
    
    // Filter to only documents that belong to this project
    const projectDocs = data.documents.filter(doc => projectDocumentIds.includes(doc.id));
    
    return {
      ...data,
      documents: projectDocs,
      total: projectDocs.length,
    };
  }, [data, projectId, localStorageVersion]);

  // Helper to save document IDs to project in localStorage
  const saveDocumentIdsToProject = (docIds: string[]) => {
    if (!projectId || docIds.length === 0) return;
    
    try {
      const stored = localStorage.getItem("uu-projects");
      if (stored) {
        const projects = JSON.parse(stored);
        const projectIndex = projects.findIndex((p: { id: string }) => p.id === projectId);
        if (projectIndex >= 0) {
          const existingIds = projects[projectIndex].documentIds || [];
          projects[projectIndex].documentIds = [...existingIds, ...docIds];
          projects[projectIndex].docCount = projects[projectIndex].documentIds.length;
          localStorage.setItem("uu-projects", JSON.stringify(projects));
          setLocalStorageVersion(v => v + 1); // Trigger re-render
        }
      }
    } catch (err) {
      console.error("Failed to save document IDs to project:", err);
    }
  };

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: (files: File[]) => api.ingestDocuments(files),
    onSuccess: (result) => {
      toast({
        title: "Documents uploaded",
        description: `Processed ${result.documents_processed} document(s) in ${result.processing_time_seconds}s`,
      });
      
      // Save new document IDs to the project
      if (result.document_ids && result.document_ids.length > 0) {
        saveDocumentIdsToProject(result.document_ids);
      }
      
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["timeline"] });
      queryClient.invalidateQueries({ queryKey: ["graph"] });
    },
    onError: (error: Error) => {
      toast({
        title: "Upload failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  // Helper to remove document ID from project in localStorage
  const removeDocumentIdFromProject = (docId: string) => {
    if (!projectId) return;
    try {
      const stored = localStorage.getItem("uu-projects");
      if (stored) {
        const projects = JSON.parse(stored);
        const projectIndex = projects.findIndex((p: { id: string }) => p.id === projectId);
        if (projectIndex >= 0) {
          const existingIds = projects[projectIndex].documentIds || [];
          projects[projectIndex].documentIds = existingIds.filter((id: string) => id !== docId);
          projects[projectIndex].docCount = projects[projectIndex].documentIds.length;
          localStorage.setItem("uu-projects", JSON.stringify(projects));
          setLocalStorageVersion(v => v + 1); // Trigger re-render
        }
      }
    } catch (err) {
      console.error("Failed to remove document ID from project:", err);
    }
  };

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteDocument(id),
    onSuccess: (_, deletedId) => {
      toast({
        title: "Document deleted",
        description: "The document has been removed.",
      });
      removeDocumentIdFromProject(deletedId);
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (error: Error) => {
      toast({
        title: "Delete failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files && files.length > 0) {
      uploadMutation.mutate(Array.from(files));
    }
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  // Filter documents by search query
  const filteredDocs = (filteredData?.documents || []).filter((doc) =>
    doc.filename.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Fetch per-document annotation stats to show label counts in table/grid
  const annotationStatsQueries = useQueries({
    queries: filteredDocs.map((doc) => ({
      queryKey: ["annotation-stats", doc.id],
      queryFn: () => api.getAnnotationStats(doc.id),
      staleTime: 0,
    })),
  });

  const annotationCountByDoc = useMemo(() => {
    const counts = new Map<string, number>();
    filteredDocs.forEach((doc, idx) => {
      const total = annotationStatsQueries[idx]?.data?.total_annotations ?? 0;
      counts.set(doc.id, total);
    });
    return counts;
  }, [filteredDocs, annotationStatsQueries]);

  const formatDate = (dateStr: string | undefined) => {
    if (!dateStr) return "—";
    try {
      return format(parseISO(dateStr), "MMM d, yyyy");
    } catch {
      return dateStr;
    }
  };

  // Auto-classify all unclassified documents asynchronously
  const handleClassifyAll = async () => {
    const unclassified = filteredDocs.filter(doc => !doc.document_type);
    if (unclassified.length === 0) {
      toast({
        title: "No Documents to Classify",
        description: "All documents are already classified",
      });
      return;
    }

    setClassifying(true);
    
    // Mark all documents as classifying
    const newClassifyingDocs = new Set(unclassified.map(doc => doc.id));
    setClassifyingDocs(newClassifyingDocs);

    // Classify all documents in parallel
    const startTime = Date.now();
    console.log(`🚀 Starting parallel classification of ${unclassified.length} documents at ${new Date().toISOString()}`);
    
    const classificationPromises = unclassified.map(async (doc, index) => {
      const docStartTime = Date.now();
      console.log(`📤 [${index + 1}/${unclassified.length}] Sending request for: ${doc.filename}`);
      
      try {
        const result = await api.autoClassifyDocument(doc.id, false);
        const elapsed = ((Date.now() - docStartTime) / 1000).toFixed(2);
        console.log(`✅ [${index + 1}/${unclassified.length}] Completed ${doc.filename} in ${elapsed}s -> ${result.document_type_name}`);
        
        // Update classifications map immediately when this doc completes
        setClassifications(prev => {
          const updated = new Map(prev);
          updated.set(doc.id, {
            type: result.document_type_name,
            typeId: result.document_type_id,
            confidence: result.confidence,
            reasoning: result.reasoning || "",
            status: 'pending',
          });
          return updated;
        });
        
        // Remove from classifying set
        setClassifyingDocs(prev => {
          const updated = new Set(prev);
          updated.delete(doc.id);
          return updated;
        });
        
        return { success: true, doc };
      } catch (error) {
        const elapsed = ((Date.now() - docStartTime) / 1000).toFixed(2);
        console.error(`❌ [${index + 1}/${unclassified.length}] Failed ${doc.filename} after ${elapsed}s:`, error);
        
        // Remove from classifying set even on error
        setClassifyingDocs(prev => {
          const updated = new Set(prev);
          updated.delete(doc.id);
          return updated;
        });
        
        return { success: false, doc, error };
      }
    });

    // Wait for all to complete
    const results = await Promise.all(classificationPromises);
    const successCount = results.filter(r => r.success).length;
    const totalElapsed = ((Date.now() - startTime) / 1000).toFixed(2);
    
    console.log(`🏁 All classifications complete in ${totalElapsed}s (${successCount}/${unclassified.length} successful)`);
    
    setClassifying(false);
    
    toast({
      title: "Classification Complete",
      description: `Successfully classified ${successCount} of ${unclassified.length} documents in ${totalElapsed}s`,
    });
  };

  // Suggest labels (schema-based annotations) for all classified documents asynchronously
  const handleSuggestLabelsAll = async () => {
    const eligible = filteredDocs.filter((doc) => !!doc.document_type);
    if (eligible.length === 0) {
      toast({
        title: "No Eligible Documents",
        description: "Classify documents first, then run label suggestions.",
      });
      return;
    }

    setSuggestingLabels(true);
    setSuggestingLabelDocs(new Set(eligible.map((doc) => doc.id)));

    const start = Date.now();
    const results = await Promise.all(
      eligible.map(async (doc) => {
        try {
          const documentTypeId = doc.document_type?.id;
          if (!documentTypeId) {
            throw new Error("Document has no document type id");
          }

          // Use the exact schema-derived labels for this document type.
          const labelsResponse = await api.listLabels(documentTypeId, false);
          const labelIds = (labelsResponse.labels || []).map((label) => label.id);
          
          // Use the exact same suggestion call shape as Label Studio.
          const response = await api.suggestAnnotations(
            doc.id,
            {
              label_ids: labelIds,
              max_suggestions: 20,
              min_confidence: 0.5,
            },
            false
          );

          let createdCount = 0;
          await Promise.all(
            (response.suggestions || []).map(async (suggestion) => {
              try {
                await api.createAnnotation(doc.id, {
                  label_id: suggestion.label_id,
                  annotation_type: "text_span",
                  start_offset: suggestion.start_offset,
                  end_offset: suggestion.end_offset,
                  text: suggestion.text,
                  metadata: suggestion.metadata,
                  created_by: "ai_batch_suggestion",
                });
                createdCount += 1;
              } catch (error) {
                // Skip duplicates/invalid suggestions and continue batch.
                console.warn(`Failed creating annotation for ${doc.filename}`, error);
              }
            })
          );

          setSuggestingLabelDocs((prev) => {
            const next = new Set(prev);
            next.delete(doc.id);
            return next;
          });
          return { success: true, docId: doc.id, created: createdCount };
        } catch (error) {
          console.error(`Failed label suggestion for ${doc.filename}`, error);
          setSuggestingLabelDocs((prev) => {
            const next = new Set(prev);
            next.delete(doc.id);
            return next;
          });
          return { success: false, docId: doc.id };
        }
      })
    );

    const successCount = results.filter((r) => r.success).length;
    const createdTotal = results.reduce((acc, r) => acc + (r.success ? r.created : 0), 0);
    const elapsed = ((Date.now() - start) / 1000).toFixed(1);

    setSuggestingLabels(false);
    queryClient.invalidateQueries({ queryKey: ["annotation-stats"] });
    queryClient.invalidateQueries({ queryKey: ["annotations"] });

    toast({
      title: "Label Suggestions Complete",
      description: `Processed ${successCount}/${eligible.length} documents, created ${createdTotal} annotations in ${elapsed}s`,
    });
  };

  // Accept a classification
  const acceptMutation = useMutation({
    mutationFn: ({ docId, typeId }: { docId: string; typeId: string }) =>
      api.classifyDocument(docId, typeId),
    onSuccess: async (_, variables) => {
      const newClassifications = new Map(classifications);
      const existing = newClassifications.get(variables.docId);
      if (existing) {
        newClassifications.set(variables.docId, { ...existing, status: 'accepted' });
        setClassifications(newClassifications);
      }
      // Force refetch instead of just invalidating
      await queryClient.refetchQueries({ queryKey: ["documents"] });
      toast({
        title: "Classification Saved",
        description: "Document classification has been saved",
      });
    },
  });

  // Reject a classification
  const handleReject = (docId: string) => {
    const newClassifications = new Map(classifications);
    const existing = newClassifications.get(docId);
    if (existing) {
      newClassifications.set(docId, { ...existing, status: 'rejected' });
      setClassifications(newClassifications);
    }
  };

  // Manual classify mutation
  const manualClassifyMutation = useMutation({
    mutationFn: ({ docId, typeId }: { docId: string; typeId: string }) =>
      api.classifyDocument(docId, typeId),
    onSuccess: async () => {
      // Force refetch instead of just invalidating
      await queryClient.refetchQueries({ queryKey: ["documents"] });
      toast({
        title: "Classification Saved",
        description: "Document has been manually classified",
      });
    },
  });

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center space-y-4">
          <p className="text-destructive">Failed to load documents</p>
          <Button variant="outline" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.txt,.md,.html,.csv,.json,.xml,.jpg,.jpeg,.png,.gif,.webp,.eml"
        className="hidden"
        onChange={handleFileSelect}
      />

      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 flex-1 max-w-md">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input 
              placeholder="Search documents..." 
              className="pl-9" 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <Button 
            variant="default" 
            className="gap-2"
            onClick={handleUploadClick}
            disabled={uploadMutation.isPending}
          >
            {uploadMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Upload className="h-4 w-4" />
            )}
            Upload
          </Button>
          <Button 
            variant="outline"
            className="gap-2"
            onClick={handleClassifyAll}
            disabled={classifying || filteredDocs.filter(d => !d.document_type).length === 0}
          >
            {classifying ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Wand2 className="h-4 w-4" />
            )}
            Classify Documents
          </Button>
          <Button
            variant="outline"
            className="gap-2"
            onClick={handleSuggestLabelsAll}
            disabled={suggestingLabels || filteredDocs.filter((d) => !d.document_type).length === filteredDocs.length}
          >
            {suggestingLabels ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Tags className="h-4 w-4" />
            )}
            Suggest Labels
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <div className="flex items-center gap-0 border rounded-md p-1 bg-background">
            <Button 
              variant="ghost" 
              size="icon" 
              className={cn("h-8 w-8 rounded-sm", viewMode === 'grid' && "bg-muted")}
              onClick={() => setViewMode('grid')}
            >
              <Grid className="h-4 w-4" />
            </Button>
            <Button 
              variant="ghost" 
              size="icon" 
              className={cn("h-8 w-8 rounded-sm", viewMode === 'list' && "bg-muted")}
              onClick={() => setViewMode('list')}
            >
              <List className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-4 text-sm text-muted-foreground">
        <span>{filteredData?.total || 0} document{(filteredData?.total || 0) !== 1 ? "s" : ""}</span>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : filteredDocs.length === 0 ? (
        <div className="flex items-center justify-center h-64 border-2 border-dashed rounded-lg">
          <div className="text-center space-y-4">
            <FileText className="h-12 w-12 text-muted-foreground mx-auto" />
            <div>
              <p className="text-lg font-medium">No documents yet</p>
              <p className="text-sm text-muted-foreground">
                Upload documents to get started
              </p>
            </div>
            <Button onClick={handleUploadClick}>
              <Upload className="h-4 w-4 mr-2" />
              Upload Documents
            </Button>
          </div>
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {filteredDocs.map((doc) => (
            <Card 
              key={doc.id} 
              className="group overflow-hidden hover:shadow-md transition-all hover:border-accent/50 cursor-pointer"
              onClick={() => onDocumentClick?.(doc.id)}
            >
              <div className="aspect-[3/4] bg-muted/30 relative border-b flex items-center justify-center">
                <FileText className="h-12 w-12 text-muted-foreground/50" />
                <div className="absolute top-2 right-2">
                  <Badge variant="outline" className="shadow-sm bg-card/90 backdrop-blur-sm">
                    {doc.file_type.toUpperCase()}
                  </Badge>
                </div>
              </div>
              <CardContent className="p-3">
                <div className="space-y-1">
                  <p className="font-medium text-sm truncate" title={doc.filename}>
                    {doc.filename}
                  </p>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3 w-3" /> 
                      {formatDate(doc.date_extracted || doc.created_at)}
                    </span>
                    <span>{(doc.token_count || 0).toLocaleString()} tokens</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="rounded-md border bg-card">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/5">
                <TableHead className="w-[300px]">Document</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Classification</TableHead>
                <TableHead>Date Extracted</TableHead>
                <TableHead>Chunks</TableHead>
                <TableHead>Tokens</TableHead>
                <TableHead>Labels</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredDocs.map((doc) => (
                <TableRow 
                  key={doc.id} 
                  className="group cursor-pointer hover:bg-muted/5"
                  onClick={() => onDocumentClick?.(doc.id)}
                >
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-8 bg-muted/20 border rounded flex items-center justify-center shrink-0">
                        <FileText className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <div className="flex flex-col">
                        <span className="font-medium text-sm truncate max-w-[200px]" title={doc.filename}>
                          {doc.filename}
                        </span>
                        <span className="text-[10px] text-muted-foreground font-mono">
                          {doc.id.slice(0, 8)}...
                        </span>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{doc.file_type.toUpperCase()}</Badge>
                  </TableCell>
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    {(() => {
                      // Show loading spinner if this document is being classified
                      if (classifyingDocs.has(doc.id)) {
                        return (
                          <div className="flex items-center gap-2">
                            <Loader2 className="h-4 w-4 animate-spin text-primary" />
                            <span className="text-sm text-muted-foreground">Classifying...</span>
                          </div>
                        );
                      }

                      // If editing this document, show dropdown
                      if (editingDoc === doc.id) {
                        return (
                          <div className="flex items-center gap-2">
                            <Select
                              onValueChange={(typeId) => {
                                manualClassifyMutation.mutate({ docId: doc.id, typeId });
                                setEditingDoc(null);
                              }}
                              onOpenChange={(open) => {
                                if (!open) setEditingDoc(null);
                              }}
                              defaultOpen
                            >
                              <SelectTrigger className="h-8 w-[200px]">
                                <SelectValue placeholder="Select type..." />
                              </SelectTrigger>
                              <SelectContent>
                                {documentTypes.map((type) => (
                                  <SelectItem key={type.id} value={type.id}>
                                    {type.name}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                        );
                      }
                      
                      const classification = classifications.get(doc.id);
                      
                      // Show existing document type if classified
                      if (doc.document_type) {
                        return (
                          <div 
                            className="flex items-center gap-2 group cursor-pointer"
                            onClick={() => setEditingDoc(doc.id)}
                          >
                            <Badge variant="default" className="bg-emerald-600">
                              {doc.document_type.name}
                            </Badge>
                            <Edit2 className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                          </div>
                        );
                      }
                      
                      if (!classification) {
                        return (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 text-muted-foreground hover:text-foreground"
                            onClick={() => setEditingDoc(doc.id)}
                          >
                            <Edit2 className="h-3 w-3 mr-1" />
                            Classify manually
                          </Button>
                        );
                      }
                      
                      if (classification.status === 'accepted') {
                        return (
                          <div 
                            className="flex items-center gap-2 group cursor-pointer"
                            onClick={() => setEditingDoc(doc.id)}
                          >
                            <Badge variant="default" className="bg-emerald-600">
                              <Check className="h-3 w-3 mr-1" />
                              {classification.type}
                            </Badge>
                            <Edit2 className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                          </div>
                        );
                      }
                      
                      if (classification.status === 'rejected') {
                        return (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 text-muted-foreground hover:text-foreground"
                            onClick={() => setEditingDoc(doc.id)}
                          >
                            <Edit2 className="h-3 w-3 mr-1" />
                            Classify manually
                          </Button>
                        );
                      }
                      
                      // Pending - show accept/reject buttons
                      return (
                        <div className="flex items-center gap-2">
                          <Badge 
                            variant="secondary" 
                            className="text-xs cursor-pointer hover:bg-secondary/80"
                            onClick={() => setEditingDoc(doc.id)}
                          >
                            {classification.type}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {Math.round(classification.confidence * 100)}%
                          </span>
                          <div className="flex gap-1">
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 w-6 p-0 text-emerald-600 hover:text-emerald-700 hover:bg-emerald-500/10"
                              onClick={() => acceptMutation.mutate({ docId: doc.id, typeId: classification.typeId })}
                              disabled={acceptMutation.isPending}
                            >
                              <Check className="h-3 w-3" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 w-6 p-0 text-red-600 hover:text-red-700 hover:bg-red-500/10"
                              onClick={() => handleReject(doc.id)}
                            >
                              <X className="h-3 w-3" />
                            </Button>
                          </div>
                        </div>
                      );
                    })()}
                  </TableCell>
                  <TableCell>
                    <span className="text-sm">
                      {doc.date_extracted ? formatDate(doc.date_extracted) : "—"}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className="font-mono text-sm">{doc.chunk_count}</span>
                  </TableCell>
                  <TableCell>
                    <span className="font-mono text-sm">
                      {(doc.token_count || 0).toLocaleString()}
                    </span>
                  </TableCell>
                  <TableCell>
                    {suggestingLabelDocs.has(doc.id) ? (
                      <div className="flex items-center gap-1 text-muted-foreground text-sm">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        suggesting...
                      </div>
                    ) : (
                      <span className="font-mono text-sm">
                        {annotationCountByDoc.get(doc.id) ?? 0}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteMutation.mutate(doc.id);
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

export default DocumentPool;
