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
import { Loader2, PlayCircle, ChevronRight, Trash2 } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  api,
  type ExtractionRequestMetrics,
  type ExtractionResult,
} from "@/lib/api";

type ExtractedField = {
  field_name: string;
  value: unknown;
  confidence?: number;
};

type CachedExtraction = {
  fields: ExtractedField[];
  requests: ExtractionRequestMetrics[];
  schema_version_id?: string | null;
  prompt_version_id?: string | null;
  extracted_at?: string;
};

const EMPTY_EXTRACTION: CachedExtraction = {
  fields: [],
  requests: [],
  schema_version_id: null,
  prompt_version_id: null,
  extracted_at: undefined,
};

function toCachedExtraction(value: unknown): CachedExtraction {
  // Backward compatibility: previous cache format stored only `fields[]`.
  if (Array.isArray(value)) {
    return { ...EMPTY_EXTRACTION, fields: value as ExtractedField[] };
  }

  if (!value || typeof value !== "object") {
    return { ...EMPTY_EXTRACTION };
  }

  const typed = value as Partial<ExtractionResult>;
  return {
    fields: Array.isArray(typed.fields) ? typed.fields : [],
    requests: Array.isArray(typed.requests) ? typed.requests : [],
    schema_version_id:
      typeof typed.schema_version_id === "string" ||
      typed.schema_version_id === null
        ? typed.schema_version_id
        : null,
    prompt_version_id:
      typeof typed.prompt_version_id === "string" ||
      typed.prompt_version_id === null
        ? typed.prompt_version_id
        : null,
    extracted_at:
      typeof typed.extracted_at === "string" ? typed.extracted_at : undefined,
  };
}

function formatLatency(latencyMs?: number | null): string {
  if (typeof latencyMs !== "number" || Number.isNaN(latencyMs)) return "—";
  if (latencyMs < 1000) return `${Math.round(latencyMs)} ms`;
  return `${(latencyMs / 1000).toFixed(2)} s`;
}

function formatTokens(totalTokens?: number | null): string {
  if (typeof totalTokens !== "number" || Number.isNaN(totalTokens)) return "—";
  return totalTokens.toLocaleString();
}

function formatCost(costUsd?: number | null): string {
  if (typeof costUsd !== "number" || Number.isNaN(costUsd)) return "—";
  return `$${costUsd.toFixed(6)}`;
}

function formatRequestTime(createdAt?: string): string {
  if (!createdAt) return "Unknown time";
  const parsed = new Date(createdAt);
  if (Number.isNaN(parsed.getTime())) return "Unknown time";
  return parsed.toLocaleString();
}

function formatSchemaLabel(schemaVersionId: string): string {
  if (schemaVersionId === "unknown") return "Unknown";
  return schemaVersionId.slice(0, 12);
}

export function ExtractionRunner({ projectId }: { projectId?: string }) {
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>("");
  const [useStructuredOutput, setUseStructuredOutput] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [localStorageVersion, setLocalStorageVersion] = useState(0);

  const [extractionCache, setExtractionCache] = useState<
    Map<string, CachedExtraction>
  >(() => {
    const stored = sessionStorage.getItem("extraction-cache");
    if (!stored) return new Map();
    const parsed = JSON.parse(stored) as Record<string, unknown>;
    return new Map(
      Object.entries(parsed).map(([docId, extraction]) => [
        docId,
        toCachedExtraction(extraction),
      ]),
    );
  });

  const selectedExtraction = selectedDocumentId
    ? extractionCache.get(selectedDocumentId) || EMPTY_EXTRACTION
    : EMPTY_EXTRACTION;
  const fields = selectedExtraction.fields || [];
  const requests = selectedExtraction.requests || [];

  const requestsBySchema = useMemo(() => {
    const grouped = new Map<string, ExtractionRequestMetrics[]>();
    for (const request of requests) {
      const schemaVersionId =
        request.schema_version_id ||
        selectedExtraction.schema_version_id ||
        "unknown";
      const existing = grouped.get(schemaVersionId) || [];
      existing.push(request);
      grouped.set(schemaVersionId, existing);
    }

    return Array.from(grouped.entries())
      .map(([schemaVersionId, schemaRequests]) => ({
        schemaVersionId,
        requests: [...schemaRequests].sort((a, b) => {
          const aTime = a.created_at ? Date.parse(a.created_at) : 0;
          const bTime = b.created_at ? Date.parse(b.created_at) : 0;
          return bTime - aTime;
        }),
      }))
      .sort((a, b) => {
        const aTime = a.requests[0]?.created_at
          ? Date.parse(a.requests[0].created_at as string)
          : 0;
        const bTime = b.requests[0]?.created_at
          ? Date.parse(b.requests[0].created_at as string)
          : 0;
        return bTime - aTime;
      });
  }, [requests, selectedExtraction.schema_version_id]);

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
      if (
        (result.fields && result.fields.length > 0) ||
        (result.requests && result.requests.length > 0)
      ) {
        setExtractionCache((prev) => {
          const updated = new Map(prev);
          updated.set(selectedDocumentId, toCachedExtraction(result));
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

  const clearUsageForDocument = () => {
    if (!selectedDocumentId) return;
    setExtractionCache((prev) => {
      const updated = new Map(prev);
      const current = updated.get(selectedDocumentId) || EMPTY_EXTRACTION;
      updated.set(selectedDocumentId, { ...current, requests: [] });
      return updated;
    });
  };

  const runExtraction = async () => {
    if (!selectedDocumentId) return;

    setIsRunning(true);
    setError(null);
    setExtractionCache((prev) => {
      const updated = new Map(prev);
      const current = updated.get(selectedDocumentId) || EMPTY_EXTRACTION;
      updated.set(selectedDocumentId, { ...current, fields: [] });
      return updated;
    });

    try {
      const result = await api.extractDocument(
        selectedDocumentId,
        !useStructuredOutput,
        useStructuredOutput,
        true,
      );
      setExtractionCache((prev) => {
        const updated = new Map(prev);
        updated.set(selectedDocumentId, toCachedExtraction(result));
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
            <Select
              value={selectedDocumentId}
              onValueChange={setSelectedDocumentId}
            >
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

          <Collapsible
            open={showAdvanced}
            onOpenChange={setShowAdvanced}
            className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-elevated)]"
          >
            <CollapsibleTrigger asChild>
              <button
                type="button"
                className="w-full px-3 py-2.5 text-left flex items-center justify-between gap-2 hover:bg-[var(--state-hover)]"
              >
                <div>
                  <p className="text-sm font-medium">Advanced options</p>
                  <p className="text-xs text-muted-foreground">
                    Retrieval and output behavior controls
                  </p>
                </div>
                <ChevronRight
                  className={`h-4 w-4 text-muted-foreground transition-transform ${showAdvanced ? "rotate-90" : ""}`}
                />
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent className="space-y-3 px-3 pb-3 border-t border-[var(--border-subtle)]">
              <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-panel)] p-3 space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <Label className="cursor-pointer">
                    Structured output mode
                  </Label>
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

              <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-panel)] p-3 space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <Label>
                    Contextual retrieval
                  </Label>
                  <Badge variant="secondary">Always on</Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  {selectedDoc?.retrieval_index_status === "completed" &&
                    selectedDoc.retrieval_chunks_count &&
                    `${selectedDoc.retrieval_chunks_count} chunks indexed`}
                  {selectedDoc?.retrieval_index_status === "processing" &&
                    "Indexing in progress. Extraction will fail until indexing completes."}
                  {selectedDoc?.retrieval_index_status === "failed" &&
                    "Indexing failed. Reindex the document before extraction."}
                  {selectedDoc?.retrieval_index_status &&
                    !["completed", "processing", "failed"].includes(
                      selectedDoc.retrieval_index_status,
                    ) &&
                    "Document is not indexed yet. Index or reindex before extraction."}
                </p>
              </div>
            </CollapsibleContent>
          </Collapsible>

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
            <div className="rounded-lg border border-[var(--status-error)]/35 bg-[var(--status-error)]/10 p-3 text-sm text-[var(--status-error)]">
              {error}
            </div>
          )}

          {!error && fields.length === 0 && requestsBySchema.length === 0 && (
            <div className="h-full min-h-[320px] rounded-lg border border-dashed border-[var(--border-strong)] flex items-center justify-center text-sm text-muted-foreground">
              No extraction results yet.
            </div>
          )}

          {requestsBySchema.length > 0 && (
            <div className="space-y-3 pb-4">
              <div className="flex items-center justify-between gap-2">
                <div className="text-xs uppercase tracking-wider text-muted-foreground font-medium">
                  Requests by Schema
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 gap-1.5 text-muted-foreground hover:text-foreground"
                  onClick={clearUsageForDocument}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Clear usage
                </Button>
              </div>
              {requestsBySchema.map((group) => (
                <div
                  key={group.schemaVersionId}
                  className="rounded-lg border border-[var(--border-subtle)] bg-card"
                >
                  <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-3 py-2">
                    <div className="text-sm font-medium">
                      Schema {formatSchemaLabel(group.schemaVersionId)}
                    </div>
                    <Badge variant="outline" className="text-[10px]">
                      {group.requests.length} request
                      {group.requests.length === 1 ? "" : "s"}
                    </Badge>
                  </div>
                  <div className="divide-y divide-[var(--border-subtle)]">
                    {group.requests.map((request) => (
                      <div key={request.request_id} className="px-3 py-2">
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
                          <span>
                            <span className="text-muted-foreground">
                              Latency:
                            </span>{" "}
                            <span className="font-medium">
                              {formatLatency(request.latency_ms)}
                            </span>
                          </span>
                          <span>
                            <span className="text-muted-foreground">
                              Tokens:
                            </span>{" "}
                            <span className="font-medium">
                              {formatTokens(request.total_tokens)}
                            </span>
                          </span>
                          <span>
                            <span className="text-muted-foreground">Cost:</span>{" "}
                            <span className="font-medium">
                              {formatCost(request.cost_usd)}
                            </span>
                          </span>
                          <span className="text-muted-foreground">
                            {formatRequestTime(request.created_at)}
                          </span>
                        </div>
                        {request.cost_note && (
                          <p className="mt-1 text-xs text-amber-700">
                            {request.cost_note}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {fields.length > 0 && (
            <div className="space-y-2">
              {fields.map((field) => (
                <Collapsible
                  key={field.field_name}
                  defaultOpen={false}
                  className="group"
                >
                  <div className="rounded-lg border border-[var(--border-subtle)] bg-card overflow-hidden">
                    <CollapsibleTrigger asChild>
                      <button className="w-full flex items-center justify-between p-3 hover:bg-muted/45 transition-colors text-left">
                        <div className="flex items-center gap-2 min-w-0">
                          <ChevronRight className="h-4 w-4 text-muted-foreground transition-transform duration-200 group-data-[state=open]:rotate-90 shrink-0" />
                          <span className="font-medium text-sm truncate">
                            {field.field_name}
                          </span>
                          {typeof field.value === "object" &&
                            Array.isArray(field.value) && (
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
