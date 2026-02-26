import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Loader2, PlayCircle, ChevronRight } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
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

  const [extractionCache, setExtractionCache] = useState<
    Map<string, ExtractedField[]>
  >(() => {
    const stored = sessionStorage.getItem("extraction-cache");
    if (!stored) return new Map();
    const parsed = JSON.parse(stored);
    return new Map(Object.entries(parsed));
  });

  const fields = selectedDocumentId
    ? extractionCache.get(selectedDocumentId) || []
    : [];

  useEffect(() => {
    const obj = Object.fromEntries(extractionCache);
    sessionStorage.setItem("extraction-cache", JSON.stringify(obj));
  }, [extractionCache]);

  useEffect(() => {
    const handleStorageChange = () => {
      setLocalStorageVersion((v) => v + 1);
    };
    window.addEventListener("storage", handleStorageChange);
    window.addEventListener("localStorageUpdate", handleStorageChange);
    return () => {
      window.removeEventListener("storage", handleStorageChange);
      window.removeEventListener("localStorageUpdate", handleStorageChange);
    };
  }, []);

  const { data: documentsData } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.listDocuments(),
  });

  const documents = useMemo(() => {
    if (!documentsData?.documents || !projectId) return [];
    const stored = localStorage.getItem("uu-projects");
    if (!stored) return [];
    const projects = JSON.parse(stored);
    const project = projects.find((p: { id: string }) => p.id === projectId);
    const projectDocumentIds: string[] = project?.documentIds || [];

    return documentsData.documents.filter((doc) =>
      projectDocumentIds.includes(doc.id),
    );
  }, [documentsData, projectId, localStorageVersion]);

  useEffect(() => {
    if (documents.length > 0 && !selectedDocumentId) {
      setSelectedDocumentId(documents[0].id);
      return;
    }
    if (
      documents.length > 0 &&
      !documents.find((doc) => doc.id === selectedDocumentId)
    ) {
      setSelectedDocumentId(documents[0].id);
      return;
    }
    if (documents.length === 0) {
      setSelectedDocumentId("");
    }
  }, [documents, selectedDocumentId]);

  useEffect(() => {
    if (!selectedDocumentId) return;
    if (extractionCache.has(selectedDocumentId)) return;

    const loadExtraction = async () => {
      const result = await api.getDocumentExtraction(selectedDocumentId);
      if (result.fields && result.fields.length > 0) {
        setExtractionCache((prev) => {
          const updated = new Map(prev);
          updated.set(selectedDocumentId, result.fields);
          return updated;
        });
      }
    };

    loadExtraction().catch(() => {
      // No prior extraction exists for this document.
    });
  }, [selectedDocumentId, extractionCache]);

  const selectedDoc = useMemo(
    () => documents.find((doc) => doc.id === selectedDocumentId),
    [documents, selectedDocumentId],
  );

  const runExtraction = async () => {
    if (!selectedDocumentId) return;

    setIsRunning(true);
    setError(null);
    setExtractionCache((prev) => {
      const updated = new Map(prev);
      updated.set(selectedDocumentId, []);
      return updated;
    });

    try {
      const result = await api.extractDocument(
        selectedDocumentId,
        !useStructuredOutput,
        useStructuredOutput,
        useRetrieval,
      );
      setExtractionCache((prev) => {
        const updated = new Map(prev);
        updated.set(selectedDocumentId, result.fields || []);
        return updated;
      });
    } catch (err: any) {
      setError(err.message || "Extraction failed");
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[380px_minmax(0,1fr)] gap-6">
      <Card className="h-fit">
        <CardHeader>
          <CardTitle>Run Extraction</CardTitle>
          <CardDescription>
            Execute extraction against project documents and inspect structured
            output.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
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

          <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-elevated)] p-3 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <Label className="cursor-pointer">Structured output mode</Label>
              <Switch
                checked={useStructuredOutput}
                onCheckedChange={setUseStructuredOutput}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              {useStructuredOutput
                ? "Schema-aligned extraction output."
                : "Annotation refinement mode output."}
            </p>
          </div>

          <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-elevated)] p-3 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <Label htmlFor="use-retrieval" className="cursor-pointer">
                Contextual retrieval
              </Label>
              <Switch
                id="use-retrieval"
                checked={useRetrieval}
                onCheckedChange={setUseRetrieval}
                disabled={selectedDoc?.retrieval_index_status !== "completed"}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              {selectedDoc?.retrieval_index_status === "completed" &&
                selectedDoc.retrieval_chunks_count &&
                `${selectedDoc.retrieval_chunks_count} chunks indexed`}
              {selectedDoc?.retrieval_index_status === "processing" &&
                "Indexing in progress"}
              {selectedDoc?.retrieval_index_status &&
                !["completed", "processing"].includes(
                  selectedDoc.retrieval_index_status,
                ) &&
                "Document is not indexed yet"}
            </p>
          </div>

          <Button
            onClick={runExtraction}
            disabled={!selectedDocumentId || isRunning}
            className="w-full gap-2"
          >
            {isRunning ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <PlayCircle className="h-4 w-4" />
            )}
            {isRunning ? "Running Extraction..." : "Run Extraction"}
          </Button>
        </CardContent>
      </Card>

      <Card className="flex flex-col min-h-[560px]">
        <CardHeader className="border-b border-[var(--border-subtle)]">
          <div className="flex items-center justify-between gap-3">
            <div>
              <CardTitle>Extraction Output</CardTitle>
              <CardDescription>
                {selectedDoc?.filename || "Select a document to inspect output"}
              </CardDescription>
            </div>
            {selectedDoc?.retrieval_index_status === "completed" && (
              <Badge variant="outline">Retrieval Indexed</Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="flex-1 overflow-y-auto py-4">
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}
          {!error && fields.length === 0 && (
            <div className="h-full min-h-[320px] rounded-lg border border-dashed border-[var(--border-strong)] flex items-center justify-center text-sm text-muted-foreground">
              No extraction results yet.
            </div>
          )}
          {fields.length > 0 && (
            <div className="space-y-2">
              {fields.map((field) => (
                <Collapsible key={field.field_name} defaultOpen={false} className="group">
                  <div className="rounded-lg border border-[var(--border-subtle)] bg-card overflow-hidden">
                    <CollapsibleTrigger asChild>
                      <button className="w-full flex items-center justify-between p-3 hover:bg-muted/45 transition-colors text-left">
                        <div className="flex items-center gap-2 min-w-0">
                          <ChevronRight className="h-4 w-4 text-muted-foreground transition-transform duration-200 group-data-[state=open]:rotate-90 shrink-0" />
                          <span className="font-medium text-sm truncate">{field.field_name}</span>
                          {typeof field.value === "object" && Array.isArray(field.value) && (
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
                      <div className="px-3 pb-3 text-sm border-t border-[var(--border-subtle)]">
                        {typeof field.value === "object" ? (
                          <pre className="bg-muted p-3 rounded text-xs overflow-x-auto max-h-[420px] overflow-y-auto mt-3">
                            {JSON.stringify(field.value, null, 2)}
                          </pre>
                        ) : (
                          <div className="text-foreground break-words pt-3">
                            {String(field.value)}
                          </div>
                        )}
                      </div>
                    </CollapsibleContent>
                  </div>
                </Collapsible>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
