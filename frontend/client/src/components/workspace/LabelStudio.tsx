import { useState, useEffect, useCallback, useRef, useMemo, useLayoutEffect, memo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { api, Document, Label, Annotation, AnnotationType, SuggestedAnnotation, TrainingStatus, FeedbackType } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { 
  ZoomIn, 
  ZoomOut, 
  FileText, 
  AlertCircle, 
  ChevronLeft, 
  ChevronRight,
  SplitSquareHorizontal,
  FileImage,
  FileCode,
  Tag,
  Loader2,
  Check,
  Type,
  MousePointer2,
  Trash2,
  Plus,
  Palette,
  X,
  Highlighter,
  Sparkles,
  CheckCircle,
  XCircle,
  Brain,
  GraduationCap,
  ThumbsUp,
  ThumbsDown,
  RefreshCw,
  Download,
  Wand2,
  FileOutput,
  KeySquare,
} from "lucide-react";

interface LabelStudioProps {
  documentId: string | null;
}

type AnnotationMode = 'select' | 'text_span' | 'entity' | 'key_value';

// Memoized PDF/document viewer so it doesn't re-mount when annotations or other state change (stops constant refresh)
interface RawDocumentViewerProps {
  fileUrl: string | null;
  fileType: string;
  filename: string;
  pdfScale: number;
  fileLoadError: boolean;
  onLoadError: () => void;
  downloadUrl: string;
}

const RawDocumentViewer = memo(function RawDocumentViewer({
  fileUrl,
  fileType,
  filename,
  pdfScale,
  fileLoadError,
  onLoadError,
  downloadUrl,
}: RawDocumentViewerProps) {
  if (!fileUrl) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-zinc-500">No file available</p>
      </div>
    );
  }

  if (fileLoadError) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <AlertCircle className="h-12 w-12 text-amber-500" />
        <div className="text-center">
          <p className="text-zinc-400">Could not load document preview</p>
          <a
            href={fileUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-400 hover:underline mt-3 inline-block"
          >
            Try opening in new tab
          </a>
        </div>
      </div>
    );
  }

  const typeLower = fileType.toLowerCase();
  if (typeLower === "pdf") {
    return (
      <object
        data={`${fileUrl}#toolbar=1&navpanes=0&zoom=${pdfScale}`}
        type="application/pdf"
        className="w-full h-full"
        onError={onLoadError}
      >
        <div className="flex flex-col items-center justify-center h-full gap-4">
          <FileText className="h-12 w-12 text-zinc-600" />
          <a
            href={fileUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-400 hover:underline"
          >
            Open PDF in new tab
          </a>
        </div>
      </object>
    );
  }

  if (["jpg", "jpeg", "png", "gif", "webp"].includes(typeLower)) {
    return (
      <div className="flex items-center justify-center h-full p-4 overflow-auto">
        <img
          src={fileUrl}
          alt={filename}
          className="max-w-full max-h-full object-contain"
          style={{ transform: `scale(${pdfScale / 100})` }}
          onError={onLoadError}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center h-full gap-4">
      <FileText className="h-16 w-16 text-zinc-600" />
      <a
        href={downloadUrl}
        className="text-sm text-blue-400 hover:underline"
      >
        Download file
      </a>
    </div>
  );
});

// Predefined colors for labels
const LABEL_COLORS = [
  '#ef4444', '#f97316', '#f59e0b', '#eab308', '#84cc16',
  '#22c55e', '#10b981', '#14b8a6', '#06b6d4', '#0ea5e9',
  '#3b82f6', '#6366f1', '#8b5cf6', '#a855f7', '#d946ef',
  '#ec4899', '#f43f5e',
];

export function LabelStudio({ documentId }: LabelStudioProps) {
  const [viewMode, setViewMode] = useState<"split" | "raw" | "extracted">("split");
  const [pdfScale, setPdfScale] = useState(100);
  const [fileLoadError, setFileLoadError] = useState(false);
  const [annotationMode, setAnnotationMode] = useState<AnnotationMode>('select');
  const [selectedLabelId, setSelectedLabelId] = useState<string | null>(null);
  const [showLabelDialog, setShowLabelDialog] = useState(false);
  const [newLabelName, setNewLabelName] = useState("");
  const [newLabelColor, setNewLabelColor] = useState(LABEL_COLORS[0]);
  const [suggestions, setSuggestions] = useState<SuggestedAnnotation[]>([]);
  const [isLoadingSuggestions, setIsLoadingSuggestions] = useState(false);
  const [keyValueKey, setKeyValueKey] = useState<string>("");
  const [showKeyValueDialog, setShowKeyValueDialog] = useState(false);
  const [pendingKeyValueSelection, setPendingKeyValueSelection] = useState<{text: string; startOffset: number; endOffset: number} | null>(null);
  const [guidedKeyIndex, setGuidedKeyIndex] = useState(0);
  
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const contentRef = useRef<HTMLPreElement>(null);
  const extractedScrollRef = useRef<HTMLDivElement>(null);
  const pendingScrollRestore = useRef<number | null>(null);

  // Restore scroll position synchronously before browser paints
  useLayoutEffect(() => {
    if (pendingScrollRestore.current !== null && extractedScrollRef.current) {
      extractedScrollRef.current.scrollTop = pendingScrollRestore.current;
      pendingScrollRestore.current = null;
    }
  });

  // Reset state when document changes
  useEffect(() => {
    setFileLoadError(false);
  }, [documentId]);

  const handlePdfLoadError = useCallback(() => setFileLoadError(true), []);

  // Fetch document content
  const { data, isLoading, error } = useQuery({
    queryKey: ["document", documentId],
    queryFn: () => documentId ? api.getDocument(documentId) : null,
    enabled: !!documentId,
    staleTime: 30000,
  });

  // Fetch document types for classification
  const { data: typesData } = useQuery({
    queryKey: ["document-types"],
    queryFn: () => api.listDocumentTypes(),
  });

  // Fetch current classification
  const { data: classificationData } = useQuery({
    queryKey: ["classification", documentId],
    queryFn: () => documentId ? api.getDocumentClassification(documentId).catch(() => null) : null,
    enabled: !!documentId,
  });

  // Fetch labels - filter by document type if classified
  const currentDocTypeId = classificationData?.classification?.document_type_id;
  const { data: labelsData } = useQuery({
    queryKey: ["labels", currentDocTypeId],
    queryFn: () => api.listLabels(currentDocTypeId, true),
  });

  // Fetch current document type details (for schema fields)
  const { data: currentDocTypeData } = useQuery({
    queryKey: ["document-type", currentDocTypeId],
    queryFn: () => currentDocTypeId ? api.getDocumentType(currentDocTypeId) : null,
    enabled: !!currentDocTypeId,
  });

  // Fetch annotations - high staleTime to prevent auto-refetches
  const { data: annotationsData } = useQuery({
    queryKey: ["annotations", documentId],
    queryFn: () => documentId ? api.listAnnotations(documentId) : null,
    enabled: !!documentId,
    staleTime: Infinity, // Never auto-refetch, we manage cache manually
    refetchOnWindowFocus: false,
  });

  // Fetch model status
  const { data: modelStatus, refetch: refetchModelStatus } = useQuery({
    queryKey: ["model-status"],
    queryFn: () => api.getModelStatus(),
    staleTime: 30000, // Refetch every 30s
  });

  // Mutations
  const classifyMutation = useMutation({
    mutationFn: ({ docId, typeId }: { docId: string; typeId: string }) =>
      api.classifyDocument(docId, { document_type_id: typeId }),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["classification", documentId] });
      toast({
        title: "Document classified",
        description: `Classified as "${result.classification.document_type_name}"`,
      });
    },
  });

  const autoClassifyMutation = useMutation({
    mutationFn: (docId: string) => api.autoClassifyDocument(docId, true),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["classification", documentId] });
      toast({
        title: "Auto-classified",
        description: `Classified as "${result.document_type_name}" (${Math.round(result.confidence * 100)}% confidence)`,
      });
    },
    onError: (error: Error) => {
      toast({ 
        title: "Auto-classification failed", 
        description: error.message, 
        variant: "destructive" 
      });
    },
  });

  const createLabelMutation = useMutation({
    mutationFn: (data: { name: string; color: string; document_type_id?: string }) => api.createLabel(data),
    onSuccess: (label) => {
      queryClient.invalidateQueries({ queryKey: ["labels"] });
      setSelectedLabelId(label.id);
      setShowLabelDialog(false);
      setNewLabelName("");
      toast({ title: "Label created", description: `Created "${label.name}"` });
    },
    onError: (error: Error) => {
      toast({ title: "Failed to create label", description: error.message, variant: "destructive" });
    },
  });

  const deleteLabelMutation = useMutation({
    mutationFn: (id: string) => api.deleteLabel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["labels"] });
      queryClient.invalidateQueries({ queryKey: ["annotations"] });
      if (selectedLabelId) setSelectedLabelId(null);
      toast({ title: "Label deleted" });
    },
  });

  // Fetch extraction result
  const { data: extractionData, refetch: refetchExtraction } = useQuery({
    queryKey: ["extraction", documentId],
    queryFn: () => documentId ? api.getDocumentExtraction(documentId).catch(() => null) : null,
    enabled: !!documentId,
    retry: false, // Don't retry on 404 - extraction may not exist yet
  });

  const extractMutation = useMutation({
    mutationFn: (docId: string) => api.extractDocument(docId, true),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["extraction", documentId] });
      toast({
        title: "Extraction complete",
        description: `Extracted ${result.fields.length} fields`,
      });
    },
    onError: (error: Error) => {
      toast({ 
        title: "Extraction failed", 
        description: error.message, 
        variant: "destructive" 
      });
    },
  });

  const createAnnotationMutation = useMutation({
    mutationFn: ({ docId, data }: { docId: string; data: Parameters<typeof api.createAnnotation>[1] }) =>
      api.createAnnotation(docId, data),
    onMutate: async ({ docId, data }) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: ["annotations", docId] });
      
      // Find the label for optimistic update
      const label = labels.find(l => l.id === data.label_id);
      
      // Snapshot the previous value
      const previousAnnotations = queryClient.getQueryData<{ annotations: Annotation[]; total: number }>(["annotations", docId]);
      
      // Create optimistic annotation with temp ID
      const tempId = `temp-${Date.now()}`;
      const newAnnotation: Annotation = {
        id: tempId,
        document_id: docId,
        label_id: data.label_id,
        label_name: label?.name,
        label_color: label?.color,
        annotation_type: data.annotation_type,
        start_offset: data.start_offset,
        end_offset: data.end_offset,
        text: data.text,
        created_at: new Date().toISOString(),
      };
      
      // Optimistically update the cache
      queryClient.setQueryData(["annotations", docId], {
        annotations: [...(previousAnnotations?.annotations || []), newAnnotation],
        total: (previousAnnotations?.total || 0) + 1,
      });
      
      return { previousAnnotations, tempId };
    },
    onSuccess: (result, variables, context) => {
      // Replace temp annotation with real one from server (no refetch needed)
      if (result?.annotation && context?.tempId) {
        queryClient.setQueryData<{ annotations: Annotation[]; total: number }>(
          ["annotations", variables.docId],
          (old) => {
            if (!old) return old;
            return {
              ...old,
              annotations: old.annotations.map(a => 
                a.id === context.tempId ? result.annotation : a
              ),
            };
          }
        );
      }
    },
    onError: (error: Error, variables, context) => {
      // Rollback on error
      if (context?.previousAnnotations) {
        queryClient.setQueryData(["annotations", variables.docId], context.previousAnnotations);
      }
      toast({ title: "Failed to create annotation", description: error.message, variant: "destructive" });
    },
  });

  const deleteAnnotationMutation = useMutation({
    mutationFn: (id: string) => api.deleteAnnotation(id),
    onMutate: async (annotationId) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: ["annotations", documentId] });
      
      // Snapshot the previous value
      const previousAnnotations = queryClient.getQueryData<{ annotations: Annotation[]; total: number }>(["annotations", documentId]);
      
      // Optimistically remove from cache
      if (previousAnnotations) {
        queryClient.setQueryData(["annotations", documentId], {
          annotations: previousAnnotations.annotations.filter(a => a.id !== annotationId),
          total: previousAnnotations.total - 1,
        });
      }
      
      return { previousAnnotations };
    },
    onError: (error: Error, annotationId, context) => {
      // Rollback on error
      if (context?.previousAnnotations) {
        queryClient.setQueryData(["annotations", documentId], context.previousAnnotations);
      }
      toast({ title: "Failed to delete annotation", variant: "destructive" });
    },
  });

  // Submit feedback for ML training
  const submitFeedbackMutation = useMutation({
    mutationFn: (data: {
      documentId: string;
      labelId: string;
      text: string;
      startOffset: number;
      endOffset: number;
      feedbackType: FeedbackType;
      source?: 'suggestion' | 'manual';
    }) => api.submitFeedback({
      document_id: data.documentId,
      label_id: data.labelId,
      text: data.text,
      start_offset: data.startOffset,
      end_offset: data.endOffset,
      feedback_type: data.feedbackType,
      source: data.source || 'suggestion',
    }),
    onSuccess: (result) => {
      if (result.should_retrain) {
        toast({ 
          title: "Ready to train!", 
          description: `${result.feedback_count} samples collected. Model can be retrained.` 
        });
      }
      refetchModelStatus();
    },
  });

  // Train model
  const trainModelMutation = useMutation({
    mutationFn: () => api.trainModel(),
    onSuccess: (result) => {
      if (result.success) {
        toast({ 
          title: "Model trained!", 
          description: result.message 
        });
      } else {
        toast({ 
          title: "Training failed", 
          description: result.message,
          variant: "destructive" 
        });
      }
      refetchModelStatus();
    },
    onError: (error: Error) => {
      toast({ 
        title: "Training error", 
        description: error.message,
        variant: "destructive" 
      });
    },
  });

  // Fetch suggestions - hold Shift to force LLM mode
  const handleFetchSuggestions = useCallback(async (e?: React.MouseEvent) => {
    if (!documentId) return;
    
    const forceLlm = e?.shiftKey || false;
    
    setIsLoadingSuggestions(true);
    try {
      const response = await api.suggestAnnotations(documentId, {
        max_suggestions: 20,
        min_confidence: 0.5,
      }, forceLlm);
      setSuggestions(response.suggestions);
      toast({ 
        title: "Suggestions ready", 
        description: `Found ${response.suggestions.length} suggestions using ${forceLlm ? 'LLM (forced)' : response.model}` 
      });
    } catch (error) {
      toast({ 
        title: "Failed to get suggestions", 
        description: error instanceof Error ? error.message : "Unknown error",
        variant: "destructive" 
      });
    } finally {
      setIsLoadingSuggestions(false);
    }
  }, [documentId, toast]);

  // Accept a suggestion as CORRECT - create annotation + positive feedback
  const handleAcceptSuggestion = useCallback((suggestion: SuggestedAnnotation) => {
    if (!documentId) return;
    
    // Create the annotation (include metadata if present)
    createAnnotationMutation.mutate({
      docId: documentId,
      data: {
        label_id: suggestion.label_id,
        annotation_type: 'text_span',
        start_offset: suggestion.start_offset,
        end_offset: suggestion.end_offset,
        text: suggestion.text,
        metadata: suggestion.metadata,
      },
    });
    
    // Submit positive feedback for ML training
    submitFeedbackMutation.mutate({
      documentId,
      labelId: suggestion.label_id,
      text: suggestion.text,
      startOffset: suggestion.start_offset,
      endOffset: suggestion.end_offset,
      feedbackType: 'accepted',
      source: 'suggestion',
    });
    
    // Remove from suggestions
    setSuggestions(prev => prev.filter(s => 
      s.start_offset !== suggestion.start_offset || s.end_offset !== suggestion.end_offset
    ));
  }, [documentId, createAnnotationMutation, submitFeedbackMutation]);

  // Mark suggestion as INCORRECT - submit negative feedback
  const handleRejectSuggestion = useCallback((suggestion: SuggestedAnnotation) => {
    if (!documentId) return;
    
    // Submit negative feedback for ML training
    submitFeedbackMutation.mutate({
      documentId,
      labelId: suggestion.label_id,
      text: suggestion.text,
      startOffset: suggestion.start_offset,
      endOffset: suggestion.end_offset,
      feedbackType: 'rejected',
      source: 'suggestion',
    });
    
    // Remove from suggestions
    setSuggestions(prev => prev.filter(s => 
      s.start_offset !== suggestion.start_offset || s.end_offset !== suggestion.end_offset
    ));
  }, [documentId, submitFeedbackMutation]);

  // Accept all suggestions
  const handleAcceptAllSuggestions = useCallback(() => {
    suggestions.forEach(suggestion => {
      handleAcceptSuggestion(suggestion);
    });
  }, [suggestions, handleAcceptSuggestion]);

  // Clear all suggestions
  const handleClearSuggestions = useCallback(() => {
    setSuggestions([]);
  }, []);

  const docData = data?.document;

  // Scroll to a suggestion/annotation in the document
  const scrollToHighlight = useCallback((startOffset: number, endOffset: number, annotationId?: string) => {
    if (!extractedScrollRef.current || !contentRef.current) return;

    // Find the mark element with matching offsets or annotation ID
    const marks = contentRef.current.querySelectorAll('mark');
    let targetMark: Element | null = null;

    for (const mark of marks) {
      const sugStart = mark.getAttribute('data-suggestion-start');
      const sugEnd = mark.getAttribute('data-suggestion-end');
      const annId = mark.getAttribute('data-annotation-id');

      // Match by annotation ID if provided
      if (annotationId && annId === annotationId) {
        targetMark = mark;
        break;
      }
      
      // Match by suggestion offsets
      if (sugStart && sugEnd) {
        if (parseInt(sugStart) === startOffset && parseInt(sugEnd) === endOffset) {
          targetMark = mark;
          break;
        }
      }
      
      // Match annotation by text position
      if (!annotationId && annId) {
        const markText = mark.textContent || '';
        const docContent = docData?.content || '';
        const markStart = docContent.indexOf(markText);
        if (markStart === startOffset) {
          targetMark = mark;
          break;
        }
      }
    }

    if (targetMark) {
      // Scroll the mark into view
      const scrollContainer = extractedScrollRef.current;
      const markRect = targetMark.getBoundingClientRect();
      const containerRect = scrollContainer.getBoundingClientRect();
      
      // Calculate the scroll position to center the mark
      const scrollTop = scrollContainer.scrollTop + (markRect.top - containerRect.top) - (containerRect.height / 3);
      
      scrollContainer.scrollTo({
        top: Math.max(0, scrollTop),
        behavior: 'smooth',
      });

      // Flash effect - add a temporary class
      targetMark.classList.add('highlight-flash');
      setTimeout(() => {
        targetMark?.classList.remove('highlight-flash');
      }, 1500);
    }
  }, [docData?.content]);
  const fileUrl = documentId ? api.getDocumentFileUrl(documentId) : null;
  const currentClassification = classificationData?.classification;
  const documentTypes = typesData?.types || [];
  const labels = labelsData?.labels || [];
  const annotations = annotationsData?.annotations || [];
  
  // Get available keys from schema for key-value mode
  const selectedLabel = labels.find(l => l.id === selectedLabelId);
  const currentDocType = currentDocTypeData?.type;
  const availableKeys: string[] = useMemo(() => {
    if (!currentDocType?.schema_fields || !selectedLabel) {
      return [];
    }

    // Find the schema field that matches the selected label (flexible: claim_data ↔ claims_data)
    const labelNorm = selectedLabel.name.toLowerCase().replace(/\s+/g, '_').replace(/_/g, '');
    const matchingField = currentDocType.schema_fields.find(field => {
      const fieldNorm = field.name.toLowerCase().replace(/\s+/g, '_').replace(/_/g, '');
      if (fieldNorm === labelNorm) return true;
      const fieldNameLower = field.name.toLowerCase().replace(/_/g, ' ');
      const labelNameLower = selectedLabel.name.toLowerCase().replace(/_/g, ' ');
      return fieldNameLower === labelNameLower ||
        labelNameLower.includes(fieldNameLower) ||
        fieldNameLower.includes(labelNameLower);
    });

    // Object field: use direct properties
    if (matchingField?.type === 'object' && matchingField.properties) {
      return Object.keys(matchingField.properties);
    }

    // Array of objects field: use item properties
    if (matchingField?.type === 'array' && matchingField.items?.type === 'object' && matchingField.items.properties) {
      return Object.keys(matchingField.items.properties);
    }

    return [];
  }, [currentDocType, selectedLabel]);

  const currentGuidedKey = useMemo(() => {
    if (availableKeys.length === 0) return "";
    return availableKeys[guidedKeyIndex] || availableKeys[0];
  }, [availableKeys, guidedKeyIndex]);

  // Reset guided flow whenever label/schema context changes
  useEffect(() => {
    setGuidedKeyIndex(0);
    setKeyValueKey("");
  }, [selectedLabelId, currentDocType?.id, availableKeys.length]);


  // Handle text selection - immediately create annotation if label is selected
  const handleTextSelection = useCallback(() => {
    if (annotationMode === 'select' || !contentRef.current || !selectedLabelId || !documentId) return;

    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) {
      return;
    }

    const rawText = selection.toString();
    const trimmedText = rawText.trim();
    if (!trimmedText) {
      return;
    }

    // Calculate how much leading whitespace was trimmed
    const leadingWhitespace = rawText.length - rawText.trimStart().length;

    // Calculate offsets relative to the content
    const range = selection.getRangeAt(0);
    
    // Find the start offset by getting text before selection
    const preRange = window.document.createRange();
    preRange.setStart(contentRef.current, 0);
    preRange.setEnd(range.startContainer, range.startOffset);
    
    // Adjust start offset to skip leading whitespace
    const startOffset = preRange.toString().length + leadingWhitespace;
    const endOffset = startOffset + trimmedText.length;

    // Save scroll position to be restored by useLayoutEffect after DOM update
    if (extractedScrollRef.current) {
      pendingScrollRestore.current = extractedScrollRef.current.scrollTop;
    }

    // For key-value mode, prompt for the key
    if (annotationMode === 'key_value') {
      if (availableKeys.length > 0) {
        const keyToUse = currentGuidedKey || availableKeys[0];
        const currentIndex = Math.min(guidedKeyIndex, availableKeys.length - 1);
        const nextIndex = (currentIndex + 1) % availableKeys.length;

        createAnnotationMutation.mutate({
          docId: documentId,
          data: {
            label_id: selectedLabelId,
            annotation_type: 'text_span',
            start_offset: startOffset,
            end_offset: endOffset,
            text: trimmedText,
            metadata: {
              key: keyToUse,
              value: trimmedText,
            },
          },
        });

        setGuidedKeyIndex(nextIndex);
        const nextKey = availableKeys[nextIndex];
        toast({
          title: `Captured "${keyToUse}"`,
          description: `Next: highlight "${nextKey}"`,
        });
        selection.removeAllRanges();
        return;
      }

      setPendingKeyValueSelection({ text: trimmedText, startOffset, endOffset });
      setShowKeyValueDialog(true);
      selection.removeAllRanges();
      return;
    }

    // Immediately create the annotation (optimistic update will trigger re-render)
    createAnnotationMutation.mutate({
      docId: documentId,
      data: {
        label_id: selectedLabelId,
        annotation_type: annotationMode as AnnotationType,
        start_offset: startOffset,
        end_offset: endOffset,
        text: trimmedText,
      },
    });

    // Clear the selection
    selection.removeAllRanges();
  }, [annotationMode, selectedLabelId, documentId, createAnnotationMutation, availableKeys, currentGuidedKey, guidedKeyIndex, toast]);

  // Memoized highlighted content - includes both annotations and suggestions
  const highlightedContent = useMemo(() => {
    if (!docData?.content) return null;
    
    const textSpanAnnotations = annotations.filter(a => a.annotation_type === 'text_span' || a.annotation_type === 'entity');
    
    // Color mapping for key-value pairs (consistent colors per key)
    const keyColors = [
      '#3b82f6', // blue
      '#10b981', // green
      '#f59e0b', // amber
      '#ef4444', // red
      '#8b5cf6', // purple
      '#ec4899', // pink
      '#06b6d4', // cyan
      '#f97316', // orange
      '#14b8a6', // teal
      '#a855f7', // violet
    ];
    
    // Collect all unique keys from annotations AND suggestions, sorted alphabetically for consistency
    const allKeys = new Set<string>();
    textSpanAnnotations.forEach(ann => {
      if (ann.metadata?.key) allKeys.add(ann.metadata.key);
    });
    suggestions.forEach(sug => {
      if (sug.metadata?.key) allKeys.add(sug.metadata.key);
    });
    const sortedKeys = Array.from(allKeys).sort();
    
    // Build stable color map
    const keyColorMap: Record<string, string> = {};
    sortedKeys.forEach((key, index) => {
      keyColorMap[key] = keyColors[index % keyColors.length];
    });
    
    // Combine annotations and suggestions into a unified list
    type Highlight = {
      type: 'annotation' | 'suggestion';
      start: number;
      end: number;
      label_name?: string;
      label_color?: string;
      text?: string;
      id?: string;
      confidence?: number;
      suggestion?: SuggestedAnnotation;
      metadata?: Record<string, any>;
    };
    
    const highlights: Highlight[] = [
      ...textSpanAnnotations.map(ann => {
        // Use key-based color if this is a key-value annotation, otherwise use label color
        const displayColor = ann.metadata?.key 
          ? keyColorMap[ann.metadata.key]
          : ann.label_color;
        
        return {
          type: 'annotation' as const,
          start: ann.start_offset || 0,
          end: ann.end_offset || 0,
          label_name: ann.label_name,
          label_color: displayColor,
          text: ann.text,
          id: ann.id,
          metadata: ann.metadata,
        };
      }),
      ...suggestions.map(sug => {
        // Use key-based color if this suggestion has metadata
        const sugColor = sug.metadata?.key 
          ? keyColorMap[sug.metadata.key] || labels.find(l => l.id === sug.label_id)?.color
          : labels.find(l => l.id === sug.label_id)?.color;
        
        return {
          type: 'suggestion' as const,
          start: sug.start_offset,
          end: sug.end_offset,
          label_name: sug.label_name,
          label_color: sugColor,
          text: sug.text,
          confidence: sug.confidence,
          suggestion: sug,
          metadata: sug.metadata,
        };
      }),
    ];
    
    if (highlights.length === 0) {
      return <span>{docData.content}</span>;
    }

    // Sort by start offset, suggestions after annotations if same position
    const sorted = [...highlights].sort((a, b) => {
      if (a.start !== b.start) return a.start - b.start;
      return a.type === 'annotation' ? -1 : 1;
    });
    
    const parts: JSX.Element[] = [];
    let lastEnd = 0;

    sorted.forEach((item, idx) => {
      // Skip if this overlaps with previous (don't double-highlight)
      if (item.start < lastEnd) return;
      
      // Add text before this highlight
      if (item.start > lastEnd) {
        parts.push(<span key={`text-${idx}`}>{docData.content.slice(lastEnd, item.start)}</span>);
      }
      
      if (item.type === 'annotation') {
        // Confirmed annotation - solid background
        // Show key name for key-value annotations
        const displayLabel = item.metadata?.key 
          ? `${item.label_name} [${item.metadata.key}]`
          : item.label_name;
        
        parts.push(
          <mark
            key={`ann-${item.id}`}
            className="annotation-mark rounded cursor-pointer hover:opacity-80"
            data-annotation-id={item.id}
            data-annotation-text={item.text}
            style={{ 
              backgroundColor: item.label_color || '#3b82f6', 
              color: 'white',
              display: 'inline',
              padding: '1px 2px',
              boxDecorationBreak: 'clone',
              WebkitBoxDecorationBreak: 'clone',
            }}
            title={`${displayLabel}: ${item.text} (click to delete)`}
          >
            {docData.content.slice(item.start, item.end)}
          </mark>
        );
      } else {
        // Suggestion - dashed border style, no fill
        parts.push(
          <mark
            key={`sug-${idx}`}
            className="suggestion-mark rounded cursor-pointer hover:opacity-90"
            data-suggestion-start={item.start}
            data-suggestion-end={item.end}
            style={{ 
              backgroundColor: 'transparent',
              border: `2px dashed ${item.label_color || '#3b82f6'}`,
              color: 'inherit',
              display: 'inline',
              padding: '1px 2px',
              boxDecorationBreak: 'clone',
              WebkitBoxDecorationBreak: 'clone',
            }}
            title={`Suggestion: ${item.label_name} (${Math.round((item.confidence || 0) * 100)}% confidence)`}
          >
            {docData.content.slice(item.start, item.end)}
          </mark>
        );
      }
      
      lastEnd = item.end;
    });

    // Add remaining text
    if (lastEnd < docData.content.length) {
      parts.push(<span key="text-end">{docData.content.slice(lastEnd)}</span>);
    }

    return <>{parts}</>;
  }, [docData?.content, annotations, suggestions, labels]);

  // Event delegation handler for clicking on annotation marks
  const handleContentClick = useCallback((e: React.MouseEvent) => {
    const target = e.target as HTMLElement;
    if (target.classList.contains('annotation-mark')) {
      const annotationId = target.dataset.annotationId;
      const annotationText = target.dataset.annotationText;
      if (annotationId && confirm(`Delete annotation "${annotationText}"?`)) {
        deleteAnnotationMutation.mutate(annotationId);
      }
    }
  }, [deleteAnnotationMutation]);

  // Check if file type is previewable
  const isPreviewable = (fileType: string) => {
    const previewable = ["pdf", "jpg", "jpeg", "png", "gif", "webp", "txt", "html", "md"];
    return previewable.includes(fileType.toLowerCase());
  };

  // No document selected
  if (!documentId) {
    return (
      <div className="flex h-full bg-zinc-950 text-zinc-50 items-center justify-center">
        <div className="text-center space-y-4">
          <FileText className="h-16 w-16 text-zinc-600 mx-auto" />
          <div>
            <h3 className="text-lg font-medium text-zinc-300">No Document Selected</h3>
            <p className="text-sm text-zinc-500 mt-1">
              Select a document from the Documents tab to view and label it
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex h-full bg-zinc-950 text-zinc-50">
        <div className="flex-1 flex flex-col border-r border-zinc-800">
          <div className="h-12 border-b border-zinc-800 flex items-center px-4 bg-zinc-900/50">
            <Skeleton className="h-4 w-48 bg-zinc-800" />
          </div>
          <div className="flex-1 bg-zinc-900/30 p-8 flex items-center justify-center">
            <Skeleton className="w-full h-full bg-zinc-800" />
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !docData) {
    return (
      <div className="flex h-full bg-zinc-950 text-zinc-50 items-center justify-center">
        <div className="text-center space-y-4">
          <AlertCircle className="h-16 w-16 text-red-500 mx-auto" />
          <div>
            <h3 className="text-lg font-medium text-zinc-300">Failed to Load Document</h3>
            <p className="text-sm text-zinc-500 mt-1">
              {error?.message || "Document not found"}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full bg-zinc-950 text-zinc-50">
      {/* Main Content Area */}
      <div className="flex-1 flex flex-col relative">
        {/* Toolbar */}
        <div className="h-12 border-b border-zinc-800 flex items-center justify-between px-4 bg-zinc-900/50">
          <div className="flex items-center gap-2">
            {/* View Mode Toggle */}
            <div className="flex items-center gap-1 bg-zinc-800 rounded-md p-1">
              <Button
                variant="ghost"
                size="sm"
                className={`h-7 px-2 ${viewMode === "split" ? "bg-zinc-700 text-white" : "text-zinc-400 hover:text-white"}`}
                onClick={() => setViewMode("split")}
                title="Split View"
              >
                <SplitSquareHorizontal className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className={`h-7 px-2 ${viewMode === "raw" ? "bg-zinc-700 text-white" : "text-zinc-400 hover:text-white"}`}
                onClick={() => setViewMode("raw")}
                title="Raw Document"
              >
                <FileImage className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className={`h-7 px-2 ${viewMode === "extracted" ? "bg-zinc-700 text-white" : "text-zinc-400 hover:text-white"}`}
                onClick={() => setViewMode("extracted")}
                title="Extracted Text"
              >
                <FileCode className="h-4 w-4" />
              </Button>
            </div>

            <Separator orientation="vertical" className="h-6 bg-zinc-700" />

            {/* Annotation Mode Toggle */}
            <div className="flex items-center gap-1 bg-zinc-800 rounded-md p-1">
              <Button
                variant="ghost"
                size="sm"
                className={`h-7 px-2 ${annotationMode === "select" ? "bg-zinc-700 text-white" : "text-zinc-400 hover:text-white"}`}
                onClick={() => setAnnotationMode("select")}
                title="Select Mode"
              >
                <MousePointer2 className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className={`h-7 px-2 ${annotationMode === "text_span" ? "bg-emerald-600 text-white" : "text-zinc-400 hover:text-white"}`}
                onClick={() => setAnnotationMode("text_span")}
                title="Text Span Annotation"
              >
                <Highlighter className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className={`h-7 px-2 ${annotationMode === "entity" ? "bg-blue-600 text-white" : "text-zinc-400 hover:text-white"}`}
                onClick={() => setAnnotationMode("entity")}
                title="Entity Annotation (NER)"
              >
                <Type className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className={`h-7 px-2 ${annotationMode === "key_value" ? "bg-purple-600 text-white" : "text-zinc-400 hover:text-white"}`}
                onClick={() => setAnnotationMode("key_value")}
                title="Key-Value Pair Annotation"
              >
                <KeySquare className="h-4 w-4" />
              </Button>
            </div>

            {/* Label Selector */}
            {annotationMode !== 'select' && (
              <>
                <Separator orientation="vertical" className="h-6 bg-zinc-700" />
                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 gap-2 bg-zinc-800 border-zinc-700"
                    >
                      {selectedLabel ? (
                        <>
                          <div 
                            className="w-3 h-3 rounded-full" 
                            style={{ backgroundColor: selectedLabel.color }}
                          />
                          {selectedLabel.name}
                        </>
                      ) : (
                        <>
                          <Tag className="h-3 w-3" />
                          Select Label
                        </>
                      )}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-56 p-2" align="start">
                    <div className="space-y-1">
                      {labels.map(label => (
                        <div
                          key={label.id}
                          className={`flex items-center justify-between px-2 py-1.5 rounded cursor-pointer hover:bg-zinc-100 ${
                            selectedLabelId === label.id ? 'bg-zinc-100' : ''
                          }`}
                          onClick={() => setSelectedLabelId(label.id)}
                        >
                          <div className="flex items-center gap-2">
                            <div 
                              className="w-3 h-3 rounded-full" 
                              style={{ backgroundColor: label.color }}
                            />
                            <span className="text-sm">{label.name}</span>
                          </div>
                          {selectedLabelId === label.id && (
                            <Check className="h-4 w-4 text-emerald-500" />
                          )}
                        </div>
                      ))}
                      <Separator className="my-2" />
                      <Button
                        variant="ghost"
                        size="sm"
                        className="w-full justify-start gap-2 text-sm"
                        onClick={() => setShowLabelDialog(true)}
                      >
                        <Plus className="h-4 w-4" />
                        Create Label
                      </Button>
                    </div>
                  </PopoverContent>
                </Popover>
              </>
            )}

            <Separator orientation="vertical" className="h-6 bg-zinc-700" />

            {/* Zoom Controls */}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-zinc-400 hover:text-white hover:bg-zinc-800"
              onClick={() => setPdfScale(Math.max(25, pdfScale - 25))}
            >
              <ZoomOut className="h-4 w-4" />
            </Button>
            <span className="text-xs text-zinc-400 w-12 text-center">{pdfScale}%</span>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-zinc-400 hover:text-white hover:bg-zinc-800"
              onClick={() => setPdfScale(Math.min(200, pdfScale + 25))}
            >
              <ZoomIn className="h-4 w-4" />
            </Button>

            <Separator orientation="vertical" className="h-6 bg-zinc-700" />

            {/* AI Suggestions - Hold Shift to force LLM */}
            <Button
              variant="outline"
              size="sm"
              className="h-7 gap-2 bg-gradient-to-r from-purple-600/20 to-blue-600/20 border-purple-500/50 text-purple-300 hover:bg-purple-600/30 hover:text-white"
              onClick={(e) => handleFetchSuggestions(e)}
              disabled={isLoadingSuggestions || labels.length === 0}
              title="Click to suggest labels. Hold Shift to force LLM mode. Note: For table fields (arrays), use Key-Value mode instead."
            >
              {isLoadingSuggestions ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : modelStatus?.is_trained ? (
                <Brain className="h-4 w-4" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              {isLoadingSuggestions ? "Analyzing..." : "Suggest Labels"}
            </Button>
            {modelStatus?.is_trained && (
              <Badge 
                variant="outline" 
                className="text-[10px] border-emerald-500/50 text-emerald-400 h-5"
                title={`ML Model: ${modelStatus.positive_samples} samples, ${modelStatus.accuracy ? `${(modelStatus.accuracy * 100).toFixed(0)}% accuracy` : 'trained'}`}
              >
                <Brain className="h-3 w-3 mr-1" />
                ML
              </Badge>
            )}
            {suggestions.length > 0 && (
              <Badge variant="secondary" className="bg-purple-600/30 text-purple-300">
                {suggestions.length} pending
              </Badge>
            )}
          </div>

          <div className="flex items-center gap-2 text-sm text-zinc-400">
            <span className="font-mono truncate max-w-[300px]" title={docData.filename}>
              {docData.filename}
            </span>
            <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400">
              {docData.file_type.toUpperCase()}
            </Badge>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1 text-zinc-400 hover:text-white"
              onClick={() => window.open(api.getExportDocumentUrl(documentId!, 'json', true), '_blank')}
              title="Export document with annotations as JSON"
            >
              <Download className="h-3.5 w-3.5" />
              Export
            </Button>
          </div>
        </div>


        {/* Content Area */}
        <div className="flex-1 flex overflow-hidden relative">
          {viewMode === "split" ? (
            <>
              <div className="flex-1 border-r border-zinc-800 bg-zinc-900/50">
                <div className="h-8 border-b border-zinc-800 flex items-center px-3 bg-zinc-900/80">
                  <FileImage className="h-3.5 w-3.5 text-zinc-500 mr-2" />
                  <span className="text-xs text-zinc-500 font-medium">Original Document</span>
                </div>
                <div className="h-[calc(100%-2rem)]">
                  <RawDocumentViewer
                    fileUrl={fileUrl}
                    fileType={docData.file_type}
                    filename={docData.filename}
                    pdfScale={pdfScale}
                    fileLoadError={fileLoadError}
                    onLoadError={handlePdfLoadError}
                    downloadUrl={documentId ? api.getDocumentFileUrl(documentId, true) : '#'}
                  />
                </div>
              </div>
              <div className="flex-1 bg-zinc-900/30">
                <div className="h-8 border-b border-zinc-800 flex items-center px-3 bg-zinc-900/80">
                  <FileCode className="h-3.5 w-3.5 text-zinc-500 mr-2" />
                  <span className="text-xs text-zinc-500 font-medium">Extracted Content</span>
                  {annotationMode !== 'select' && (
                    <span className="ml-2 text-xs text-emerald-400">
                      {selectedLabelId
                        ? (
                          annotationMode === 'key_value' && availableKeys.length > 0
                            ? `(Highlight "${currentGuidedKey}")`
                            : "(Highlight text to annotate)"
                        )
                        : "(Select a label first)"}
                    </span>
                  )}
                </div>
                <div ref={extractedScrollRef} className="h-[calc(100%-2rem)] overflow-auto">
                  <div className="p-6">
                    <div 
                      className="bg-white text-zinc-900 rounded-lg shadow-xl p-8 min-h-[500px] overflow-x-auto"
                      onMouseUp={handleTextSelection}
                      onClick={handleContentClick}
                    >
                      <pre 
                        ref={contentRef}
                        className="font-mono text-xs leading-relaxed whitespace-pre-wrap break-words"
                      >
                        {highlightedContent}
                      </pre>
                    </div>
                  </div>
                </div>
              </div>
            </>
          ) : viewMode === "raw" ? (
            <div className="flex-1 bg-zinc-900/50">
              <RawDocumentViewer
                fileUrl={fileUrl}
                fileType={docData.file_type}
                filename={docData.filename}
                pdfScale={pdfScale}
                fileLoadError={fileLoadError}
                onLoadError={handlePdfLoadError}
                downloadUrl={documentId ? api.getDocumentFileUrl(documentId, true) : '#'}
              />
            </div>
          ) : (
            <div ref={extractedScrollRef} className="flex-1 bg-zinc-900/30 overflow-auto">
              <div className="p-6">
                <div 
                  className="bg-white text-zinc-900 rounded-lg shadow-xl p-8 min-h-[500px] overflow-x-auto"
                  onMouseUp={handleTextSelection}
                  onClick={handleContentClick}
                >
                  <pre 
                    ref={contentRef}
                    className="font-mono text-xs leading-relaxed whitespace-pre-wrap break-words"
                  >
                    {highlightedContent}
                  </pre>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Sidebar */}
      <div className="w-80 flex flex-col bg-zinc-900 border-l border-zinc-800">
        <div className="h-12 border-b border-zinc-800 flex items-center justify-between px-4 font-medium text-sm">
          <span>Annotations</span>
          <Badge variant="secondary" className="bg-zinc-800">
            {annotations.length}
          </Badge>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-4 space-y-4">
            {/* Document Classification */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide flex items-center gap-2">
                  <Tag className="h-3.5 w-3.5" />
                  Document Type
                </h4>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 gap-1 text-xs text-purple-400 hover:text-purple-300 hover:bg-purple-500/10"
                  onClick={() => documentId && autoClassifyMutation.mutate(documentId)}
                  disabled={autoClassifyMutation.isPending || documentTypes.length === 0}
                  title="Auto-classify using AI"
                >
                  {autoClassifyMutation.isPending ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Wand2 className="h-3 w-3" />
                  )}
                  Auto
                </Button>
              </div>
              <Select
                value={currentClassification?.document_type_id || ""}
                onValueChange={(typeId) => {
                  if (documentId && typeId) {
                    classifyMutation.mutate({ docId: documentId, typeId });
                  }
                }}
                disabled={classifyMutation.isPending || documentTypes.length === 0}
              >
                <SelectTrigger className="bg-zinc-950 border-zinc-700 text-zinc-200">
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
              {currentClassification && currentClassification.confidence && (
                <div className="text-[10px] text-zinc-500 flex items-center gap-1">
                  <span>Confidence: {Math.round(currentClassification.confidence * 100)}%</span>
                  {currentClassification.labeled_by === 'auto-llm' && (
                    <Badge variant="outline" className="text-[8px] h-4 border-purple-500/50 text-purple-400">
                      AI
                    </Badge>
                  )}
                </div>
              )}
            </div>

            <Separator className="bg-zinc-800" />

            {/* Labels */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                  Labels
                </h4>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={() => setShowLabelDialog(true)}
                >
                  <Plus className="h-3 w-3" />
                </Button>
              </div>
              <div className="space-y-1">
                {labels.map(label => (
                  <div
                    key={label.id}
                    className={`group flex items-center justify-between px-2 py-1.5 rounded cursor-pointer hover:bg-zinc-800 ${
                      selectedLabelId === label.id ? 'bg-zinc-800' : ''
                    }`}
                    onClick={() => setSelectedLabelId(label.id)}
                  >
                    <div className="flex items-center gap-2">
                      <div 
                        className="w-3 h-3 rounded-full" 
                        style={{ backgroundColor: label.color }}
                      />
                      <span className="text-sm text-zinc-300">{label.name}</span>
                      {!label.document_type_id && (
                        <Badge variant="outline" className="text-[8px] h-4 border-zinc-600 text-zinc-500">
                          Global
                        </Badge>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-5 w-5 opacity-0 group-hover:opacity-100 hover:bg-red-500/20 hover:text-red-400"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteLabelMutation.mutate(label.id);
                      }}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
                {labels.length === 0 && (
                  <p className="text-xs text-zinc-500 text-center py-2">
                    No labels defined
                  </p>
                )}
              </div>
            </div>

            {/* Guided key-value prompt: show "Highlight claim_item" then "Highlight claim_amount" etc. */}
            {annotationMode === 'key_value' && selectedLabel && availableKeys.length > 0 && (
              <>
                <Separator className="bg-zinc-800" />
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                    Key-Value: {selectedLabel.name}
                  </h4>
                  <div className="p-3 rounded-lg bg-purple-950/40 border border-purple-500/40">
                    <p className="text-xs text-zinc-400 mb-1">Current step</p>
                    <p className="text-sm font-medium text-purple-200">
                      Highlight &quot;{currentGuidedKey}&quot;
                    </p>
                    {availableKeys.length > 1 && (
                      <p className="text-[10px] text-zinc-500 mt-2">
                        Order: {availableKeys.map((k, i) => (
                          <span key={k}>
                            {i === guidedKeyIndex ? (
                              <span className="text-purple-400 font-medium">{k}</span>
                            ) : (
                              <span className="text-zinc-600">{k}</span>
                            )}
                            {i < availableKeys.length - 1 && ', '}
                          </span>
                        ))}
                      </p>
                    )}
                  </div>
                </div>
              </>
            )}

            {/* Suggestions Section */}
            {suggestions.length > 0 && (
              <>
                <Separator className="bg-zinc-800" />
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-semibold text-purple-400 uppercase tracking-wide flex items-center gap-2">
                      <Brain className="h-3.5 w-3.5" />
                      AI Suggestions ({suggestions.length})
                    </h4>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-[10px] text-emerald-400 hover:bg-emerald-500/20"
                        onClick={handleAcceptAllSuggestions}
                      >
                        Accept All
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-[10px] text-zinc-500 hover:bg-zinc-800"
                        onClick={handleClearSuggestions}
                      >
                        Clear
                      </Button>
                    </div>
                  </div>
                  {/* Note about key-value mode for table fields */}
                  {currentDocType?.schema_fields?.some(f => f.type === 'array' && f.items?.type === 'object') && (
                    <div className="p-2 rounded bg-amber-950/20 border border-amber-500/30 text-[10px] text-amber-300">
                      <span className="font-semibold">💡 Tip:</span> For table fields, use <span className="font-mono bg-purple-600/30 px-1 rounded">Key-Value mode</span> (purple button) instead of suggestions for better accuracy.
                    </div>
                  )}
                  <div className="space-y-2">
                    {suggestions.map((sug, idx) => {
                      const label = labels.find(l => l.id === sug.label_id);
                      return (
                        <div
                          key={`sug-${idx}`}
                          className="p-2 rounded bg-purple-950/30 border border-purple-500/30 border-dashed group cursor-pointer hover:bg-purple-950/50 transition-colors"
                          onClick={() => scrollToHighlight(sug.start_offset, sug.end_offset)}
                          title="Click to scroll to this suggestion"
                        >
                          <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center gap-2">
                              <div 
                                className="w-2 h-2 rounded-full" 
                                style={{ backgroundColor: label?.color || '#8b5cf6' }}
                              />
                              <span className="text-xs font-medium text-purple-300">
                                {sug.label_name}
                                {sug.metadata?.key && (
                                  <span className="ml-1 text-[10px] opacity-70">[{sug.metadata.key}]</span>
                                )}
                              </span>
                              <Badge variant="outline" className="text-[9px] border-purple-500/50 text-purple-400 h-4 px-1">
                                {Math.round(sug.confidence * 100)}%
                              </Badge>
                            </div>
                            <div className="flex items-center gap-1">
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-5 w-5 hover:bg-emerald-500/20 hover:text-emerald-400"
                                onClick={(e) => { e.stopPropagation(); handleAcceptSuggestion(sug); }}
                                title="Correct - accept and train"
                              >
                                <ThumbsUp className="h-3.5 w-3.5" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-5 w-5 hover:bg-red-500/20 hover:text-red-400"
                                onClick={(e) => { e.stopPropagation(); handleRejectSuggestion(sug); }}
                                title="Incorrect - reject and train"
                              >
                                <ThumbsDown className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          </div>
                          <p className="text-[11px] text-purple-200/70 line-clamp-2">
                            "{sug.text}"
                          </p>
                          {sug.reasoning && (
                            <p className="text-[10px] text-purple-400/50 mt-1 italic">
                              {sug.reasoning}
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </>
            )}

            <Separator className="bg-zinc-800" />

            {/* Model Training Status */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide flex items-center gap-2">
                  <GraduationCap className="h-3.5 w-3.5" />
                  ML Model
                </h4>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-5 w-5"
                  onClick={() => refetchModelStatus()}
                  title="Refresh status"
                >
                  <RefreshCw className="h-3 w-3" />
                </Button>
              </div>
              
              {modelStatus && (
                <div className="p-3 rounded bg-zinc-950 border border-zinc-800 space-y-2">
                  {/* Status indicator */}
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-zinc-400">Status</span>
                    {modelStatus.is_trained ? (
                      <Badge className="bg-emerald-600/20 text-emerald-400 border-emerald-500/50">
                        Trained
                      </Badge>
                    ) : modelStatus.ready_to_train ? (
                      <Badge className="bg-amber-600/20 text-amber-400 border-amber-500/50">
                        Ready to Train
                      </Badge>
                    ) : (
                      <Badge className="bg-zinc-700 text-zinc-400">
                        Collecting Data
                      </Badge>
                    )}
                  </div>
                  
                  {/* Sample counts */}
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-zinc-500">Positive</span>
                      <p className="font-medium text-emerald-400">{modelStatus.positive_samples}</p>
                    </div>
                    <div>
                      <span className="text-zinc-500">Negative</span>
                      <p className="font-medium text-red-400">{modelStatus.negative_samples}</p>
                    </div>
                  </div>
                  
                  {/* Progress to training */}
                  {!modelStatus.is_trained && (
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-zinc-500">Training progress</span>
                        <span className="text-zinc-400">
                          {modelStatus.positive_samples}/{modelStatus.min_samples_required}
                        </span>
                      </div>
                      <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-gradient-to-r from-purple-500 to-blue-500 transition-all"
                          style={{ 
                            width: `${Math.min(100, (modelStatus.positive_samples / modelStatus.min_samples_required) * 100)}%` 
                          }}
                        />
                      </div>
                    </div>
                  )}
                  
                  {/* Accuracy if trained */}
                  {modelStatus.is_trained && modelStatus.accuracy !== null && (
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-zinc-500">Accuracy</span>
                      <span className="text-emerald-400 font-medium">
                        {(modelStatus.accuracy * 100).toFixed(1)}%
                      </span>
                    </div>
                  )}
                  
                  {/* Train button */}
                  {modelStatus.ready_to_train && (
                    <Button
                      size="sm"
                      className="w-full h-7 mt-2 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500"
                      onClick={() => trainModelMutation.mutate()}
                      disabled={trainModelMutation.isPending}
                    >
                      {trainModelMutation.isPending ? (
                        <Loader2 className="h-3 w-3 mr-2 animate-spin" />
                      ) : (
                        <GraduationCap className="h-3 w-3 mr-2" />
                      )}
                      {trainModelMutation.isPending ? "Training..." : "Train Model"}
                    </Button>
                  )}
                  
                  {/* Last trained */}
                  {modelStatus.last_trained_at && (
                    <p className="text-[10px] text-zinc-600 text-center">
                      Last trained: {new Date(modelStatus.last_trained_at).toLocaleDateString()}
                    </p>
                  )}
                </div>
              )}
            </div>

            <Separator className="bg-zinc-800" />

            {/* Annotations List */}
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Annotations ({annotations.length})
              </h4>
              <div className="space-y-2">
                {annotations.map(ann => (
                  <div
                    key={ann.id}
                    className="p-2 rounded bg-zinc-950 border border-zinc-800 hover:border-zinc-700 group cursor-pointer transition-colors"
                    onClick={() => ann.start_offset !== undefined && ann.end_offset !== undefined && scrollToHighlight(ann.start_offset, ann.end_offset, ann.id)}
                    title="Click to scroll to this annotation"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <div 
                          className="w-2 h-2 rounded-full" 
                          style={{ backgroundColor: ann.label_color || '#3b82f6' }}
                        />
                        <span className="text-xs font-medium text-zinc-400">
                          {ann.label_name}
                        </span>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-5 w-5 opacity-0 group-hover:opacity-100 hover:bg-red-500/20 hover:text-red-400"
                        onClick={(e) => { e.stopPropagation(); deleteAnnotationMutation.mutate(ann.id); }}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                    <p className="text-[11px] text-zinc-500 line-clamp-2">
                      "{ann.text}"
                    </p>
                    <span className="text-[10px] text-zinc-600">
                      {ann.annotation_type} • chars {ann.start_offset}-{ann.end_offset}
                    </span>
                  </div>
                ))}
                {annotations.length === 0 && (
                  <p className="text-xs text-zinc-500 text-center py-4">
                    No annotations yet. Select text to annotate.
                  </p>
                )}
              </div>
            </div>

            <Separator className="bg-zinc-800" />

            {/* Extracted Data */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide flex items-center gap-2">
                  <FileOutput className="h-3.5 w-3.5" />
                  Extracted Data
                </h4>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 gap-1 text-xs text-blue-400 hover:text-blue-300 hover:bg-blue-500/10"
                  onClick={() => documentId && extractMutation.mutate(documentId)}
                  disabled={extractMutation.isPending || !currentClassification}
                  title={!currentClassification ? "Classify document first" : "Run extraction"}
                >
                  {extractMutation.isPending ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Wand2 className="h-3 w-3" />
                  )}
                  Extract
                </Button>
              </div>
              
              {!currentClassification ? (
                <p className="text-xs text-zinc-500 text-center py-2">
                  Classify this document first to enable extraction.
                </p>
              ) : extractionData ? (
                <div className="p-3 rounded bg-zinc-950 border border-zinc-800 space-y-2">
                  {extractionData.fields.map((field, idx) => (
                    <div key={idx} className="text-xs">
                      <span className="text-zinc-500">{field.field_name}:</span>
                      <span className="text-zinc-200 ml-2">
                        {typeof field.value === 'object' 
                          ? JSON.stringify(field.value)
                          : String(field.value)
                        }
                      </span>
                    </div>
                  ))}
                  {extractionData.fields.length === 0 && (
                    <p className="text-xs text-zinc-500">No fields extracted</p>
                  )}
                </div>
              ) : (
                <p className="text-xs text-zinc-500 text-center py-2">
                  Click "Extract" to run structured extraction.
                </p>
              )}
            </div>
          </div>
        </ScrollArea>

        <div className="p-3 border-t border-zinc-800 flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="flex-1 border-zinc-700 text-zinc-300 hover:bg-zinc-800 text-xs"
          >
            <ChevronLeft className="h-3 w-3 mr-1" />
            Prev
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="flex-1 border-zinc-700 text-zinc-300 hover:bg-zinc-800 text-xs"
          >
            Next
            <ChevronRight className="h-3 w-3 ml-1" />
          </Button>
        </div>
      </div>

      {/* Create Label Dialog */}
      <Dialog open={showLabelDialog} onOpenChange={setShowLabelDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Label</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Label Name</label>
              <Input
                placeholder="e.g., Person, Date, Amount, Company"
                value={newLabelName}
                onChange={(e) => setNewLabelName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Color</label>
              <div className="flex flex-wrap gap-2">
                {LABEL_COLORS.map(color => (
                  <button
                    key={color}
                    className={`w-8 h-8 rounded-full border-2 transition-transform ${
                      newLabelColor === color ? 'border-white scale-110' : 'border-transparent'
                    }`}
                    style={{ backgroundColor: color }}
                    onClick={() => setNewLabelColor(color)}
                  />
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowLabelDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => createLabelMutation.mutate({ name: newLabelName, color: newLabelColor })}
              disabled={!newLabelName.trim() || createLabelMutation.isPending}
            >
              {createLabelMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Key-Value Input Dialog */}
      <Dialog open={showKeyValueDialog} onOpenChange={(open) => {
        setShowKeyValueDialog(open);
      }}>
        <DialogContent className="bg-zinc-900 border-zinc-800">
          <DialogHeader>
            <DialogTitle>Specify Key for Value</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Selected Value</label>
              <div className="bg-zinc-800 p-3 rounded-md text-sm font-mono">
                {pendingKeyValueSelection?.text}
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Key Name</label>
              {!selectedLabel ? (
                <div className="p-3 rounded bg-amber-950/20 border border-amber-500/30 text-xs text-amber-300">
                  Please select a label first (from the dropdown above)
                </div>
              ) : availableKeys.length > 0 ? (
                <Select value={keyValueKey} onValueChange={setKeyValueKey}>
                  <SelectTrigger className="bg-zinc-800 border-zinc-700">
                    <SelectValue placeholder="Select a key..." />
                  </SelectTrigger>
                  <SelectContent>
                    {availableKeys.map(key => (
                      <SelectItem key={key} value={key}>
                        {key}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <Input
                  placeholder="e.g., claim_item, claim_cost, etc."
                  value={keyValueKey}
                  onChange={(e) => setKeyValueKey(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && keyValueKey.trim() && pendingKeyValueSelection) {
                      createAnnotationMutation.mutate({
                        docId: documentId!,
                        data: {
                          label_id: selectedLabelId!,
                          annotation_type: 'text_span',
                          start_offset: pendingKeyValueSelection.startOffset,
                          end_offset: pendingKeyValueSelection.endOffset,
                          text: pendingKeyValueSelection.text,
                          metadata: {
                            key: keyValueKey.trim(),
                            value: pendingKeyValueSelection.text,
                          },
                        },
                      });
                      setShowKeyValueDialog(false);
                      setKeyValueKey('');
                      setPendingKeyValueSelection(null);
                    }
                  }}
                  className="bg-zinc-800 border-zinc-700"
                />
              )}
            </div>
          </div>
          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={() => {
                setShowKeyValueDialog(false);
                setKeyValueKey('');
                setPendingKeyValueSelection(null);
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (keyValueKey.trim() && pendingKeyValueSelection) {
                  createAnnotationMutation.mutate({
                    docId: documentId!,
                    data: {
                      label_id: selectedLabelId!,
                      annotation_type: 'text_span',
                      start_offset: pendingKeyValueSelection.startOffset,
                      end_offset: pendingKeyValueSelection.endOffset,
                      text: pendingKeyValueSelection.text,
                      metadata: {
                        key: keyValueKey.trim(),
                        value: pendingKeyValueSelection.text,
                      },
                    },
                  });
                  setShowKeyValueDialog(false);
                  setKeyValueKey('');
                  setPendingKeyValueSelection(null);
                }
              }}
              disabled={!keyValueKey.trim()}
            >
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* CSS for highlight flash animation */}
      <style>{`
        @keyframes highlightFlash {
          0%, 100% { opacity: 1; }
          25% { opacity: 0.3; }
          50% { opacity: 1; }
          75% { opacity: 0.3; }
        }
        .highlight-flash {
          animation: highlightFlash 0.5s ease-in-out 3;
          box-shadow: 0 0 10px 4px rgba(168, 85, 247, 0.6);
        }
      `}</style>
    </div>
  );
}
