import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Loader2, PlayCircle, ChevronDown, ChevronRight } from "lucide-react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { api } from "@/lib/api";

type ExtractedField = {
  field_name: string;
  value: unknown;
  confidence?: number;
};

export function ExtractionRunner({ projectId }: { projectId?: string }) {
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>("");
  const [useStructuredOutput, setUseStructuredOutput] = useState(true);
  const [useRetrieval, setUseRetrieval] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [localStorageVersion, setLocalStorageVersion] = useState(0);
  
  // Persist extraction results per document
  const [extractionCache, setExtractionCache] = useState<Map<string, ExtractedField[]>>(() => {
    try {
      const stored = sessionStorage.getItem('extraction-cache');
      if (stored) {
        const parsed = JSON.parse(stored);
        return new Map(Object.entries(parsed));
      }
    } catch (e) {
      console.error('Failed to load extraction cache:', e);
    }
    return new Map();
  });

  // Get fields for currently selected document
  const fields = selectedDocumentId ? (extractionCache.get(selectedDocumentId) || []) : [];

  // Save cache to sessionStorage whenever it changes
  useEffect(() => {
    try {
      const obj = Object.fromEntries(extractionCache);
      sessionStorage.setItem('extraction-cache', JSON.stringify(obj));
    } catch (e) {
      console.error('Failed to save extraction cache:', e);
    }
  }, [extractionCache]);

  // Listen for localStorage changes
  useEffect(() => {
    const handleStorageChange = () => {
      setLocalStorageVersion(v => v + 1);
    };
    window.addEventListener('storage', handleStorageChange);
    // Also listen for custom event from same window
    window.addEventListener('localStorageUpdate', handleStorageChange);
    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('localStorageUpdate', handleStorageChange);
    };
  }, []);

  // Fetch documents with React Query for automatic cache invalidation
  const { data: documentsData } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.listDocuments(),
  });

  // Filter documents by project
  const documents = useMemo(() => {
    if (!documentsData?.documents || !projectId) return [];
    
    // Get document IDs for this project from localStorage
    let projectDocumentIds: string[] = [];
    try {
      const stored = localStorage.getItem("uu-projects");
      if (stored) {
        const projects = JSON.parse(stored);
        const project = projects.find((p: { id: string }) => p.id === projectId);
        projectDocumentIds = project?.documentIds || [];
        
        console.log('[ExtractionRunner] Project:', projectId);
        console.log('[ExtractionRunner] Project document IDs:', projectDocumentIds);
        console.log('[ExtractionRunner] All documents:', documentsData.documents.length);
      }
    } catch (e) {
      console.error('[ExtractionRunner] Error reading localStorage:', e);
      projectDocumentIds = [];
    }
    
    const filtered = documentsData.documents.filter(doc => projectDocumentIds.includes(doc.id));
    console.log('[ExtractionRunner] Filtered documents:', filtered.length);
    
    return filtered;
  }, [documentsData, projectId, localStorageVersion]);

  // Update selected document when documents change
  useEffect(() => {
    if (documents.length > 0 && !selectedDocumentId) {
      setSelectedDocumentId(documents[0].id);
    } else if (documents.length > 0 && !documents.find(d => d.id === selectedDocumentId)) {
      // Selected document was deleted, select first available
      setSelectedDocumentId(documents[0].id);
    } else if (documents.length === 0) {
      setSelectedDocumentId("");
    }
  }, [documents, selectedDocumentId]);

  // Load extraction from backend when document changes (if not in cache)
  useEffect(() => {
    if (!selectedDocumentId) return;
    if (extractionCache.has(selectedDocumentId)) return; // Already in cache
    
    // Try to load from backend
    const loadExtraction = async () => {
      try {
        const result = await api.getDocumentExtraction(selectedDocumentId);
        if (result.fields && result.fields.length > 0) {
          setExtractionCache(prev => {
            const updated = new Map(prev);
            updated.set(selectedDocumentId, result.fields);
            return updated;
          });
        }
      } catch (e) {
        // No extraction exists yet, that's fine
      }
    };
    
    loadExtraction();
  }, [selectedDocumentId, extractionCache]);

  const selectedDoc = useMemo(
    () => documents.find((d) => d.id === selectedDocumentId),
    [documents, selectedDocumentId]
  );

  const runExtraction = async () => {
    if (!selectedDocumentId) return;
    setIsRunning(true);
    setError(null);
    
    // Clear fields for this document while loading
    setExtractionCache(prev => {
      const updated = new Map(prev);
      updated.set(selectedDocumentId, []);
      return updated;
    });
    
    try {
      const data = await api.extractDocument(
        selectedDocumentId,
        !useStructuredOutput,
        useStructuredOutput,
        useRetrieval
      );
      
      // Save to cache
      setExtractionCache(prev => {
        const updated = new Map(prev);
        updated.set(selectedDocumentId, data.fields || []);
        return updated;
      });
    } catch (e: any) {
      setError(e.message || "Extraction failed");
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Live Extraction Runner</CardTitle>
          <CardDescription>
            Runs real extraction against a stored document.
            {projectId ? <> Project ID: <span className="font-mono">{projectId}</span></> : null}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2 md:col-span-2">
              <Label>Document</Label>
              <Select value={selectedDocumentId} onValueChange={setSelectedDocumentId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a document" />
                </SelectTrigger>
                <SelectContent>
                  {documents.map((doc) => (
                    <SelectItem key={doc.id} value={doc.id}>
                      {doc.filename}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Mode</Label>
              <div className="flex items-center gap-2 rounded-md border px-3 py-2 h-10">
                <Switch checked={useStructuredOutput} onCheckedChange={setUseStructuredOutput} />
                <span className="text-sm">{useStructuredOutput ? "Structured output" : "Annotation refinement"}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Switch 
                id="use-retrieval"
                checked={useRetrieval} 
                onCheckedChange={setUseRetrieval}
                disabled={selectedDoc?.retrieval_index_status !== 'completed'}
              />
              <Label htmlFor="use-retrieval" className="text-sm cursor-pointer">
                Use Contextual Retrieval
              </Label>
              {selectedDoc && selectedDoc.retrieval_index_status === 'completed' && selectedDoc.retrieval_chunks_count && (
                <span className="text-xs text-muted-foreground">({selectedDoc.retrieval_chunks_count} chunks indexed)</span>
              )}
              {selectedDoc && selectedDoc.retrieval_index_status === 'processing' && (
                <span className="text-xs text-muted-foreground">(indexing...)</span>
              )}
              {selectedDoc && selectedDoc.retrieval_index_status !== 'completed' && selectedDoc.retrieval_index_status !== 'processing' && (
                <span className="text-xs text-muted-foreground">(not indexed)</span>
              )}
            </div>
          </div>

          <Button onClick={runExtraction} disabled={!selectedDocumentId || isRunning} className="gap-2">
            {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
            Run Extraction
          </Button>
        </CardContent>
      </Card>

      {selectedDoc && (
        <Card>
          <CardHeader>
            <CardTitle>Document</CardTitle>
            <CardDescription>{selectedDoc.filename}</CardDescription>
          </CardHeader>
        </Card>
      )}

      <Card className="flex flex-col max-h-[1200px]">
        <CardHeader className="flex-shrink-0">
          <CardTitle>Extracted Fields</CardTitle>
          <CardDescription>Real extraction output from backend.</CardDescription>
        </CardHeader>
        <CardContent className="flex-1 overflow-y-auto min-h-0">
          {error ? <div className="text-sm text-red-600">{error}</div> : null}
          {!error && fields.length === 0 ? (
            <div className="text-sm text-muted-foreground">No extraction results yet.</div>
          ) : null}
          {fields.length > 0 ? (
            <div className="space-y-2 pr-2 pb-4">
              {fields.map((field) => (
                <Collapsible key={field.field_name} defaultOpen={false} className="group">
                  <div className="rounded-lg border bg-card overflow-hidden">
                    <CollapsibleTrigger asChild>
                      <button className="w-full flex items-center justify-between p-3 hover:bg-muted/50 transition-colors text-left">
                        <div className="flex items-center gap-2">
                          <ChevronRight className="h-4 w-4 text-muted-foreground transition-transform duration-200 group-data-[state=open]:rotate-90" />
                          <span className="font-medium text-sm">{field.field_name}</span>
                          {typeof field.value === 'object' && Array.isArray(field.value) && (
                            <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                              {field.value.length} items
                            </span>
                          )}
                        </div>
                        {field.confidence && (
                          <span className="text-xs text-muted-foreground">
                            {Math.round(field.confidence * 100)}%
                          </span>
                        )}
                      </button>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <div className="px-3 pb-3 text-sm border-t">
                        {typeof field.value === 'object' ? (
                          <pre className="bg-muted p-3 rounded text-xs overflow-x-auto max-h-[500px] overflow-y-auto mt-3">
                            {JSON.stringify(field.value, null, 2)}
                          </pre>
                        ) : (
                          <div className="text-foreground break-words pt-3">{String(field.value)}</div>
                        )}
                      </div>
                    </CollapsibleContent>
                  </div>
                </Collapsible>
              ))}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
