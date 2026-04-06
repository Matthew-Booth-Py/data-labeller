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
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Loader2,
  PlayCircle,
  ChevronRight,
  Trash2,
  Search,
  FileSearch,
  Copy,
  Check,
  Table2,
} from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  api,
  type ExtractionRequestMetadata,
  type ExtractionRequestMetrics,
  type ExtractionResult,
  type FieldCoverageInfo,
  type RetrievalSearchResult,
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
  request_metadata?: ExtractionRequestMetadata | null;
};

const EMPTY_EXTRACTION: CachedExtraction = {
  fields: [],
  requests: [],
  schema_version_id: null,
  prompt_version_id: null,
  extracted_at: undefined,
  request_metadata: null,
};

function toCachedExtraction(value: unknown): CachedExtraction {
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
    request_metadata: typed.request_metadata ?? null,
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

function coverageStatusVariant(
  status: string,
): "default" | "secondary" | "destructive" | "outline" {
  if (status === "found" || status === "complete") return "default";
  if (status === "partial") return "secondary";
  if (status === "not_found" || status === "missing") return "destructive";
  return "outline";
}

function RetrievalTracePanel({
  metadata,
}: {
  metadata: ExtractionRequestMetadata;
}) {
  const coverage = metadata.coverage_by_field;
  const sourcePages = metadata.source_page_numbers;

  return (
    <div className="space-y-3">
      {sourcePages && sourcePages.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Pages used:</span>
          {sourcePages.map((p) => (
            <Badge key={p} variant="outline" className="text-[10px] px-1.5">
              {p}
            </Badge>
          ))}
          {metadata.strategy && (
            <span className="ml-auto opacity-60">{metadata.strategy}</span>
          )}
        </div>
      )}

      {coverage && Object.keys(coverage).length > 0 && (
        <div className="space-y-1.5">
          {Object.entries(coverage).map(
            ([fieldName, info]: [string, FieldCoverageInfo]) => (
              <Collapsible
                key={fieldName}
                defaultOpen={false}
                className="group"
              >
                <div className="rounded-md border border-[var(--border-subtle)] bg-card overflow-hidden">
                  <CollapsibleTrigger asChild>
                    <button
                      type="button"
                      className="w-full flex items-center justify-between px-3 py-2 hover:bg-muted/40 transition-colors text-left gap-2"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0 transition-transform duration-200 group-data-[state=open]:rotate-90" />
                        <span className="text-xs font-medium truncate">
                          {fieldName}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {info.top_page_numbers?.length > 0 && (
                          <span className="text-[10px] text-muted-foreground">
                            p.{info.top_page_numbers.join(", ")}
                          </span>
                        )}
                        <Badge
                          variant={coverageStatusVariant(info.status)}
                          className="text-[10px] px-1.5 py-0"
                        >
                          {info.status}
                        </Badge>
                      </div>
                    </button>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <div className="px-3 pb-2.5 pt-1.5 border-t border-[var(--border-subtle)] space-y-2 text-xs">
                      {info.queries_used?.length > 0 && (
                        <div>
                          <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium mb-1">
                            Queries ({info.rounds} round
                            {info.rounds !== 1 ? "s" : ""})
                          </p>
                          <ul className="space-y-0.5">
                            {info.queries_used.map((q, i) => (
                              <li
                                key={i}
                                className="text-muted-foreground bg-muted/50 rounded px-2 py-1 font-mono text-[10px] break-words"
                              >
                                {q}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {info.scores?.length > 0 && (
                        <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                          <span>Scores:</span>
                          {info.scores.slice(0, 5).map((s, i) => (
                            <span key={i} className="font-mono">
                              {s.toFixed(3)}
                            </span>
                          ))}
                          {info.scores.length > 5 && (
                            <span>+{info.scores.length - 5} more</span>
                          )}
                        </div>
                      )}
                      {info.asset_labels?.filter(Boolean).length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {info.asset_labels.filter(Boolean).map((label, i) => (
                            <Badge
                              key={i}
                              variant="secondary"
                              className="text-[10px] px-1.5 py-0"
                            >
                              {label}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  </CollapsibleContent>
                </div>
              </Collapsible>
            ),
          )}
        </div>
      )}
    </div>
  );
}

interface ParsedTable {
  groupHeaders: string[];
  columnHeaders: string[];
  rows: string[][];
}

function parseMarkdownTable(text: string): ParsedTable | null {
  const lines = text
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.startsWith("|") && l.endsWith("|"));

  if (lines.length < 3) return null;

  const parseCells = (line: string): string[] =>
    line
      .split("|")
      .slice(1, -1)
      .map((c) => c.trim());

  const isSeparator = (line: string) => /^\|[\s\-:|]+\|$/.test(line);
  const sepIdx = lines.findIndex(isSeparator);
  if (sepIdx < 1) return null;

  // Row before separator = group headers (e.g. "| | GAAP | | | Non-GAAP | |")
  const groupHeaders = parseCells(lines[sepIdx - 1]);

  // Row(s) after separator before data are column headers
  // Find the next separator or treat first post-sep row as column headers
  const postSep = lines.slice(sepIdx + 1);
  const nextSepIdx = postSep.findIndex(isSeparator);

  let columnHeaders: string[];
  let dataLines: string[];

  if (nextSepIdx === 0) {
    // Back-to-back separators — treat first post-sep row as col headers
    columnHeaders = parseCells(postSep[1] ?? "");
    dataLines = postSep.slice(2);
  } else if (nextSepIdx > 0) {
    // Second header row then another separator
    columnHeaders = parseCells(postSep[0]);
    dataLines = postSep.slice(nextSepIdx + 1);
  } else {
    // Single header row (standard markdown)
    columnHeaders = groupHeaders;
    dataLines = postSep;
  }

  const rows = dataLines
    .filter((l) => !isSeparator(l))
    .map(parseCells)
    .filter((r) => r.some((c) => c.length > 0));

  if (rows.length === 0) return null;
  return { groupHeaders, columnHeaders, rows };
}

function tableToJson(parsed: ParsedTable): Record<string, string>[] {
  // Build combined header keys: prefer columnHeaders, fall back to index
  const keys = parsed.columnHeaders.map((h, i) => {
    if (h) return h;
    const group = parsed.groupHeaders[i];
    return group ? `${group}_${i}` : `col_${i}`;
  });

  return parsed.rows.map((row) => {
    const obj: Record<string, string> = {};
    keys.forEach((key, i) => {
      obj[key || `col_${i}`] = row[i] ?? "";
    });
    return obj;
  });
}

function CopyButton({ getValue }: { getValue: () => string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(getValue()).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors"
    >
      {copied ? (
        <Check className="h-3 w-3 text-green-500" />
      ) : (
        <Copy className="h-3 w-3" />
      )}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function ParsedTableView({ parsed }: { parsed: ParsedTable }) {
  const json = tableToJson(parsed);

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded border border-[var(--border-subtle)]">
        <table className="text-[10px] w-full border-collapse">
          {parsed.groupHeaders.some((h) => h) && (
            <thead>
              <tr className="bg-muted/60">
                {parsed.groupHeaders.map((h, i) => (
                  <th
                    key={i}
                    className="px-2 py-1 text-left font-semibold border-b border-[var(--border-subtle)] text-muted-foreground whitespace-nowrap"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
          )}
          <tbody>
            <tr className="bg-muted/30">
              {parsed.columnHeaders.map((h, i) => (
                <td
                  key={i}
                  className="px-2 py-1 font-semibold border-b border-[var(--border-subtle)] whitespace-nowrap"
                >
                  {h}
                </td>
              ))}
            </tr>
            {parsed.rows.map((row, ri) => (
              <tr
                key={ri}
                className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-muted/20"
              >
                {row.map((cell, ci) => (
                  <td
                    key={ci}
                    className="px-2 py-1 whitespace-nowrap font-mono"
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center gap-3 justify-end">
        <CopyButton
          getValue={() => parsed.rows.map((r) => r.join("\t")).join("\n")}
        />
        <CopyButton getValue={() => JSON.stringify(json, null, 2)} />
        <span className="text-[10px] text-muted-foreground ml-auto">
          {parsed.rows.length} rows · {parsed.columnHeaders.length} cols
        </span>
      </div>
    </div>
  );
}

function SearchResultItem({ result }: { result: RetrievalSearchResult }) {
  const [expanded, setExpanded] = useState(false);
  const [tableView, setTableView] = useState(false);

  const text = result.text || result.original_text || "";
  const preview = text.length > 240 ? text.slice(0, 240) + "…" : text;
  const parsed = useMemo(() => parseMarkdownTable(text), [text]);
  const isTable = result.asset_type === "table" || parsed !== null;

  // Auto-show table view for table chunks
  const showTable = tableView && parsed !== null;

  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-card p-3 space-y-2 text-xs">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 flex-wrap">
          {result.page_number != null && (
            <Badge variant="outline" className="text-[10px] px-1.5">
              Page {result.page_number}
            </Badge>
          )}
          {result.asset_type && (
            <Badge variant="secondary" className="text-[10px] px-1.5">
              {result.asset_type}
              {result.asset_label ? `: ${result.asset_label}` : ""}
            </Badge>
          )}
          <span className="text-muted-foreground">
            chunk #{result.chunk_index}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {isTable && parsed && (
            <button
              type="button"
              onClick={() => setTableView(!tableView)}
              className={`flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                tableView
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Table2 className="h-3 w-3" />
              Table
            </button>
          )}
          <span className="font-mono font-medium">
            {result.score.toFixed(3)}
          </span>
        </div>
      </div>

      {result.context && !showTable && (
        <p className="text-[10px] text-muted-foreground italic border-l-2 border-[var(--border-subtle)] pl-2">
          {result.context}
        </p>
      )}

      {showTable && parsed ? (
        <ParsedTableView parsed={parsed} />
      ) : (
        <>
          <p className="text-foreground/80 break-words whitespace-pre-wrap leading-relaxed">
            {expanded ? text : preview}
          </p>
          {text.length > 240 && (
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              className="text-[10px] text-primary underline-offset-2 hover:underline"
            >
              {expanded ? "Show less" : "Show full chunk"}
            </button>
          )}
        </>
      )}
    </div>
  );
}

export function ExtractionRunner({ projectId }: { projectId?: string }) {
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>("");
  const [useStructuredOutput, setUseStructuredOutput] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [retrievalQuery, setRetrievalQuery] = useState("");
  const [retrievalResults, setRetrievalResults] = useState<
    RetrievalSearchResult[]
  >([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchExecuted, setSearchExecuted] = useState(false);

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

  const { data: documentsData } = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.listDocuments(),
  });

  const { data: projectData } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.getProject(projectId || ""),
    enabled: !!projectId,
  });

  const documents = useMemo(() => {
    if (!documentsData?.documents || !projectId) return [];
    const projectDocumentIds = projectData?.project?.document_ids || [];

    return documentsData.documents.filter((doc) =>
      projectDocumentIds.includes(doc.id),
    );
  }, [documentsData, projectData, projectId]);

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

  // Reset search results when document changes
  useEffect(() => {
    setRetrievalResults([]);
    setSearchExecuted(false);
    setSearchError(null);
  }, [selectedDocumentId]);

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

  const runSearch = async () => {
    if (!retrievalQuery.trim() || !selectedDocumentId) return;
    setIsSearching(true);
    setSearchError(null);
    try {
      const result = await api.searchDocuments(
        retrievalQuery.trim(),
        selectedDocumentId,
        8,
      );
      setRetrievalResults(result.results);
      setSearchExecuted(true);
    } catch (err: any) {
      setSearchError(err.message || "Search failed");
    } finally {
      setIsSearching(false);
    }
  };

  const hasRetrievalTrace =
    !!selectedExtraction.request_metadata?.coverage_by_field &&
    Object.keys(selectedExtraction.request_metadata.coverage_by_field).length >
      0;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[380px_minmax(0,1fr)] gap-6">
      {/* Left: controls */}
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

          {selectedDocumentId && (
            <div
              className={`rounded-lg border px-3 py-2.5 text-xs space-y-0.5 ${
                selectedDoc?.document_type
                  ? "border-[var(--border-subtle)] bg-[var(--surface-elevated)]"
                  : "border-[var(--status-warning)]/40 bg-[var(--status-warning)]/10"
              }`}
            >
              <p className="font-medium text-muted-foreground uppercase tracking-wider text-[10px]">
                Active schema
              </p>
              {selectedDoc?.document_type ? (
                <p className="font-medium">{selectedDoc.document_type.name}</p>
              ) : (
                <p className="text-[var(--status-warning)] font-medium">
                  Not classified — extraction will fail. Classify this document
                  in the Documents tab first.
                </p>
              )}
            </div>
          )}

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

      {/* Right: output + retrieval debug stacked */}
      <div className="flex flex-col gap-6 min-w-0">
        {/* Extraction Output */}
        <Card className="flex flex-col min-h-[560px]">
          <CardHeader className="border-b border-[var(--border-subtle)]">
            <div className="flex items-center justify-between gap-3">
              <div>
                <CardTitle>Extraction Output</CardTitle>
                <CardDescription>
                  {selectedDoc?.filename ||
                    "Select a document to inspect output"}
                </CardDescription>
              </div>
              {selectedDoc?.retrieval_index_status === "completed" && (
                <Badge variant="outline">Retrieval Indexed</Badge>
              )}
            </div>
          </CardHeader>
          <CardContent className="flex-1 overflow-y-auto py-4 space-y-4">
            {error && (
              <div className="rounded-lg border border-[var(--status-error)]/35 bg-[var(--status-error)]/10 p-3 text-sm text-[var(--status-error)]">
                {error}
              </div>
            )}

            {!error && fields.length === 0 && (
              <div className="h-full min-h-[320px] rounded-lg border border-dashed border-[var(--border-strong)] flex items-center justify-center text-sm text-muted-foreground">
                No extraction results yet.
              </div>
            )}

            {/* Retrieval Trace (from last extraction's request_metadata) */}
            {hasRetrievalTrace && selectedExtraction.request_metadata && (
              <div className="space-y-2">
                <div className="text-xs uppercase tracking-wider text-muted-foreground font-medium">
                  Retrieval Trace
                </div>
                <RetrievalTracePanel
                  metadata={selectedExtraction.request_metadata}
                />
              </div>
            )}

            {fields.length > 0 && (
              <div className="space-y-2">
                <div className="text-xs uppercase tracking-wider text-muted-foreground font-medium">
                  Fields
                </div>
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

        {/* Retrieval Search / Debug */}
        <Card>
          <CardHeader className="border-b border-[var(--border-subtle)] pb-4">
            <div className="flex items-center gap-2">
              <FileSearch className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Test Retrieval</CardTitle>
            </div>
            <CardDescription>
              Query the retrieval index directly to verify what chunks would be
              retrieved for a given search term.
            </CardDescription>
          </CardHeader>
          <CardContent className="py-4 space-y-4">
            <div className="flex gap-2">
              <Input
                placeholder={
                  selectedDocumentId
                    ? "e.g. financial highlights gross margin Q3 2024"
                    : "Select a document first"
                }
                value={retrievalQuery}
                onChange={(e) => setRetrievalQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") runSearch();
                }}
                disabled={!selectedDocumentId || isSearching}
                className="flex-1 text-sm"
              />
              <Button
                onClick={runSearch}
                disabled={
                  !selectedDocumentId || !retrievalQuery.trim() || isSearching
                }
                variant="secondary"
                className="gap-2 shrink-0"
              >
                {isSearching ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Search className="h-4 w-4" />
                )}
                Search
              </Button>
            </div>

            {searchError && (
              <div className="rounded-lg border border-[var(--status-error)]/35 bg-[var(--status-error)]/10 p-3 text-sm text-[var(--status-error)]">
                {searchError}
              </div>
            )}

            {searchExecuted &&
              retrievalResults.length === 0 &&
              !searchError && (
                <div className="rounded-lg border border-dashed border-[var(--border-strong)] py-8 flex items-center justify-center text-sm text-muted-foreground">
                  No chunks matched this query.
                </div>
              )}

            {retrievalResults.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <p className="text-xs uppercase tracking-wider text-muted-foreground font-medium">
                    {retrievalResults.length} chunk
                    {retrievalResults.length !== 1 ? "s" : ""} retrieved
                  </p>
                  <p className="text-[10px] text-muted-foreground">
                    sorted by score ↓
                  </p>
                </div>
                {retrievalResults.map((result, i) => (
                  <SearchResultItem
                    key={`${result.chunk_id ?? result.chunk_index}-${i}`}
                    result={result}
                  />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
